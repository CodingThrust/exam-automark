from __future__ import annotations

"""Local-only browser UI for a private root-cause review queue.

This reviewer is intentionally separate from question-level gold entry and
from final error-book diagnoses.  It displays only approved anonymous pages
listed in a private queue, writes a separate private human-review document,
and never invokes a model or contacts a remote service.
"""

import argparse
import hashlib
import json
import secrets
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import sha256_file  # noqa: E402
from benchmark.core.error_audit import PRIMARY_CAUSE_MECHANISMS  # noqa: E402
from benchmark.core.error_review_queue import (  # noqa: E402
    empty_human_review_document,
    update_human_review_document,
    validate_human_review_document,
    validate_private_output_under_root,
    validate_root_cause_review_queue,
    write_human_review_document,
)
from benchmark.core.scoped_anonymous_images import (  # noqa: E402
    SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SNAPSHOT_RECORD_TYPE,
    SNAPSHOT_SCHEMA_VERSION,
)


_MAX_REQUEST_BYTES = 1_000_000


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a localhost-only browser UI for representative root-cause "
            "review. No model is called."
        )
    )
    parser.add_argument(
        "--queue",
        type=Path,
        required=True,
        help="private root-cause-review-queue JSON created by build_error_review_queue.py",
    )
    parser.add_argument(
        "--scoped-image-root",
        type=Path,
        required=True,
        help="approved private scoped anonymous-image snapshot root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="gitignored private human-root-cause-review JSON to create/update",
    )
    parser.add_argument("--port", type=int, default=8771)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    try:
        store = ErrorCaseReviewStore(
            queue_path=args.queue,
            scoped_image_root=args.scoped_image_root,
            review_output=args.output,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    access_token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), _handler_class(store, access_token=access_token)
    )
    print(
        "Open this local, single-session URL in a browser (do not share it): "
        f"http://127.0.0.1:{args.port}/?token={access_token}"
    )
    print("This tool is a human root-cause review aid only; no model is called.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Local root-cause reviewer stopped.")
    finally:
        server.server_close()
    return 0


class ErrorCaseReviewStore:
    """Lock-protected local state for one immutable queue and review document."""

    def __init__(
        self,
        *,
        queue_path: Path,
        scoped_image_root: Path,
        review_output: Path,
        private_root: Path | None = None,
    ) -> None:
        self.queue_path = _require_regular_file(queue_path, "root-cause review queue")
        self.scoped_image_root = _require_regular_directory(
            scoped_image_root, "scoped image root"
        )
        self.review_output = review_output.resolve()
        self.private_root = (private_root or (REPO_ROOT / "Data")).resolve()
        validate_private_output_under_root(
            self.review_output, private_root=self.private_root
        )
        self._queue = _load_json_object(self.queue_path, "root-cause review queue")
        validate_root_cause_review_queue(self._queue)
        self._queue_sha256 = sha256_file(self.queue_path)
        self._items = _queue_items(self._queue)
        self._images, self._binding_warning = _load_and_validate_snapshot(
            root=self.scoped_image_root,
            queue=self._queue,
            items=self._items,
        )
        self._allowed_image_paths = frozenset(self._images)
        self._snapshot_manifest_path = (
            self.scoped_image_root / SNAPSHOT_MANIFEST_RELATIVE_PATH
        )
        self._image_sha256 = {
            relative_path: sha256_file(image_path)
            for relative_path, image_path in self._images.items()
        }
        self._lock = threading.Lock()
        if self.review_output.exists():
            self._document = _load_json_object(
                self.review_output, "existing human root-cause review"
            )
            validate_human_review_document(
                document=self._document,
                queue_path=self.queue_path,
                queue=self._queue,
            )
            self._document_sha256: str | None = sha256_file(self.review_output)
        else:
            self._document = empty_human_review_document(
                queue_path=self.queue_path, queue=self._queue
            )
            self._document_sha256 = None

    def state(self) -> dict[str, Any]:
        """Return only private, anonymous queue fields required by the local page."""

        with self._lock:
            self._assert_snapshot_unchanged()
            reviews = {
                str(review["queue_item_id"]): dict(review)
                for review in self._document["reviews"]
                if isinstance(review, Mapping)
            }
            items = []
            reviewed_count = 0
            needs_more_evidence_count = 0
            for item in self._items:
                item_copy = dict(item)
                review = reviews.get(str(item["queue_item_id"]))
                if review is not None:
                    if review.get("review_status") == "reviewed":
                        reviewed_count += 1
                    elif review.get("review_status") == "needs_more_evidence":
                        needs_more_evidence_count += 1
                item_copy["human_review"] = review
                items.append(item_copy)
            return {
                "queue": {
                    "queue_id": self._queue["queue_id"],
                    "course_id": self._queue["provenance"]["course_id"],
                    "assessment_id": self._queue["provenance"]["assessment_id"],
                    "review_guidance": self._queue["review_guidance"],
                    "review_context": self._queue["review_context"],
                    "review_form": self._queue["review_form"],
                },
                "binding": {"warning": self._binding_warning},
                "items": items,
                "summary": {
                    "item_count": len(items),
                    "reviewed_count": reviewed_count,
                    "needs_more_evidence_count": needs_more_evidence_count,
                    "unreviewed_count": len(items)
                    - reviewed_count
                    - needs_more_evidence_count,
                },
            }

    def image_path(self, relative_path: str) -> Path:
        self._assert_snapshot_unchanged()
        if relative_path not in self._allowed_image_paths:
            raise ValueError("requested image is not bound to the private review queue")
        image_path = self._images[relative_path]
        if not image_path.is_file() or image_path.is_symlink():
            raise FileNotFoundError(image_path)
        if sha256_file(image_path) != self._image_sha256[relative_path]:
            raise ValueError("approved snapshot image changed after local reviewer startup")
        return image_path

    def save_review(self, payload: Mapping[str, Any]) -> None:
        item_id = _required_text(payload, "queue_item_id")
        review_status = _required_text(payload, "review_status")
        reviewer = _required_text(payload, "reviewer")
        reviewed_at = _required_text(payload, "reviewed_at")
        mechanism_code = _optional_text(payload, "mechanism_code")
        review_rationale = _optional_text(payload, "review_rationale")
        typical_case = payload.get("typical_case")
        if not isinstance(typical_case, bool):
            raise ValueError("typical_case must be true or false")

        if review_status == "reviewed":
            if not mechanism_code:
                raise ValueError("a reviewed item needs a root-cause mechanism")
            primary_cause = _primary_cause_for_mechanism(mechanism_code)
        elif review_status == "needs_more_evidence":
            mechanism_code = None
            primary_cause = None
        else:
            raise ValueError("review_status must be reviewed or needs_more_evidence")

        review = {
            "queue_item_id": item_id,
            "review_status": review_status,
            "mechanism_code": mechanism_code,
            "primary_cause": primary_cause,
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "review_rationale": review_rationale,
            "typical_case": typical_case,
        }
        with self._lock:
            self._assert_snapshot_unchanged()
            self._reject_external_review_change()
            updated = update_human_review_document(
                document=self._document,
                queue_path=self.queue_path,
                queue=self._queue,
                review=review,
            )
            write_human_review_document(
                output_path=self.review_output,
                document=updated,
                private_root=self.private_root,
            )
            self._document = updated
            self._document_sha256 = sha256_file(self.review_output)

    def _assert_snapshot_unchanged(self) -> None:
        if not self._snapshot_manifest_path.is_file() or sha256_file(
            self._snapshot_manifest_path
        ) != self._queue["provenance"]["data_snapshot_sha256"]:
            raise ValueError(
                "approved snapshot manifest changed after local reviewer startup; "
                "restart only after revalidating the review queue"
            )

    def _reject_external_review_change(self) -> None:
        if self._document_sha256 is None:
            if self.review_output.exists():
                raise ValueError(
                    "the review output appeared after this local reviewer started; "
                    "restart before saving so no external review is overwritten"
                )
            return
        if not self.review_output.is_file() or sha256_file(self.review_output) != self._document_sha256:
            raise ValueError(
                "the review output changed outside this local reviewer; restart before saving "
                "so no external review is overwritten"
            )


def _queue_items(queue: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_items = queue.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("root-cause review queue items must be a list")
    items = tuple(dict(item) for item in raw_items if isinstance(item, Mapping))
    if len(items) != len(raw_items):
        raise ValueError("root-cause review queue contains a malformed item")
    return items


def _load_and_validate_snapshot(
    *,
    root: Path,
    queue: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Path], str | None]:
    manifest_path = root / SNAPSHOT_MANIFEST_RELATIVE_PATH
    manifest = _load_json_object(manifest_path, "scoped anonymous-image snapshot manifest")
    if manifest.get("record_type") != SNAPSHOT_RECORD_TYPE:
        raise ValueError("scoped image root is not an approved anonymous snapshot")
    if manifest.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("unsupported scoped anonymous-image snapshot schema")
    if sha256_file(manifest_path) != queue["provenance"]["data_snapshot_sha256"]:
        raise ValueError(
            "scoped image snapshot manifest does not match the review queue data snapshot"
        )
    raw_images = manifest.get("images")
    if not isinstance(raw_images, list):
        raise ValueError("scoped image snapshot manifest needs an images list")

    manifest_images: dict[str, Mapping[str, Any]] = {}
    for entry in raw_images:
        if not isinstance(entry, Mapping):
            raise ValueError("scoped image snapshot has a malformed image entry")
        relative_path = entry.get("snapshot_image")
        if not isinstance(relative_path, str) or relative_path in manifest_images:
            raise ValueError("scoped image snapshot has duplicate or invalid image paths")
        manifest_images[relative_path] = entry

    # The exact manifest hash and every image hash are the binding that matters
    # for a review queue.  A legacy snapshot may have been created before an
    # assessment identifier was normalized; surface that label discrepancy to
    # the reviewer rather than substituting a different snapshot or silently
    # treating its text label as stronger than the immutable hash.
    binding_warning: str | None = None
    if manifest.get("assessment_id") != queue["provenance"]["assessment_id"]:
        binding_warning = (
            "Legacy snapshot assessment label differs from the queue label; "
            "the exact snapshot-manifest hash and every displayed image hash "
            "were verified. Do not substitute another snapshot."
        )

    result: dict[str, Path] = {}
    for item in items:
        image = item["image"]
        assert isinstance(image, Mapping)
        relative_path = image["relative_path"]
        assert isinstance(relative_path, str)
        entry = manifest_images.get(relative_path)
        if entry is None:
            raise ValueError("review queue names an image absent from the approved snapshot")
        if entry.get("anonymous_id") != item["anonymous_student_id"]:
            raise ValueError("review queue image/student binding differs from approved snapshot")
        if entry.get("page_suffix") != image["page_suffix"]:
            raise ValueError("review queue image/page binding differs from approved snapshot")
        declared_hash = entry.get("sha256")
        if not isinstance(declared_hash, str):
            raise ValueError("approved snapshot image is missing its hash")
        candidate = _safe_snapshot_image(root, relative_path)
        if sha256_file(candidate) != declared_hash:
            raise ValueError("approved snapshot image changed after queue creation")
        result[relative_path] = candidate
    return result, binding_warning


def _safe_snapshot_image(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if not _is_within(candidate, root) or not candidate.is_file() or candidate.is_symlink():
        raise ValueError("approved snapshot image path is unsafe or missing")
    if candidate.suffix.lower() != ".png":
        raise ValueError("approved snapshot image is not a PNG")
    return candidate


def _handler_class(
    store: ErrorCaseReviewStore, *, access_token: str
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._token_is_valid(request):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            if request.path == "/":
                self._send_bytes(
                    HTTPStatus.OK,
                    _HTML.encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            elif request.path == "/api/state":
                try:
                    self._send_json(HTTPStatus.OK, store.state())
                except ValueError as error:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            elif request.path.startswith("/images/"):
                try:
                    image_path = store.image_path(
                        unquote(request.path.removeprefix("/images/"))
                    )
                except (FileNotFoundError, ValueError):
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "image not found"})
                    return
                self._send_bytes(HTTPStatus.OK, image_path.read_bytes(), "image/png")
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._token_is_valid(request):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            if request.path != "/api/review":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > _MAX_REQUEST_BYTES:
                    raise ValueError(
                        "request body must be between 1 and 1,000,000 bytes"
                    )
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("JSON object required")
                store.save_review(payload)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._send_json(HTTPStatus.OK, {"status": "saved"})

        def _token_is_valid(self, request: Any) -> bool:
            provided = parse_qs(request.query, keep_blank_values=True).get("token", [""])[0]
            return isinstance(provided, str) and secrets.compare_digest(provided, access_token)

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
            self._send_bytes(
                status,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                ),
                "application/json; charset=utf-8",
            )

        def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _primary_cause_for_mechanism(mechanism_code: str) -> str:
    matches = [
        primary_cause
        for primary_cause, mechanisms in PRIMARY_CAUSE_MECHANISMS.items()
        if mechanism_code in mechanisms
    ]
    if len(matches) != 1:
        raise ValueError("invalid root-cause mechanism")
    return matches[0]


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = _optional_text(payload, key)
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _require_regular_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"{label} must be a regular file: {path}")
    return resolved


def _require_regular_directory(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir() or resolved.is_symlink():
        raise ValueError(f"{label} must be a regular directory: {path}")
    return resolved


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


_HTML = r"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>匿名错题根因复核 / Root-cause review</title>
<style>
body { font:14px system-ui,sans-serif; margin:16px; color:#18212f; background:#f7f9fc; }
#top { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
button,select,input,textarea { font:inherit; padding:6px 8px; } button { cursor:pointer; }
#main { display:grid; grid-template-columns:minmax(0,1fr) 410px; gap:16px; align-items:start; }
#image-card,#panel { background:#fff; border:1px solid #d4dce8; padding:12px; border-radius:8px; }
#image { width:100%; border:1px solid #9aa8bc; background:#fff; display:block; }
.hint { color:#526175; line-height:1.55; } .warning { color:#8a5600; font-weight:600; } .ok { color:#20724d; font-weight:600; }
.condition { border-top:1px solid #e3e8f0; padding:9px 0; } .condition:first-child { border-top:0; }
details { margin-top:6px; } pre { white-space:pre-wrap; overflow-wrap:anywhere; margin:6px 0; font:12px ui-monospace,monospace; }
textarea { width:100%; min-height:80px; box-sizing:border-box; } label { display:block; margin:8px 0; }
#message { white-space:pre-wrap; } .complete { color:#20724d; } .pending { color:#8a5600; }
@media (max-width:1000px) { #main { grid-template-columns:1fr; } }
</style>
<body><h1>匿名错题根因复核 / Private root-cause review</h1>
<p class="hint">仅在本机运行；只显示已绑定的匿名原图和私有开发集结果，不调用模型、不上传数据。先从原图和 gold 判断，再查看模型理由。这里是首轮抽样复核，不是最终全量 diagnoses。</p>
<p id="binding" class="ok">Private queue and approved image snapshot loaded.</p>
<div id="top"><label>审核人 / Reviewer <input id="reviewer" placeholder="姓名或缩写 / name or initials"></label><span id="summary"></span><button id="prev">上一例 / Previous</button><select id="item"></select><button id="next">下一例 / Next</button></div>
<div id="main"><div id="image-card"><h2 id="image-title"></h2><img id="image" alt="anonymous assessment page"><p class="hint">建议顺序：①核对原图和 gold；②比较三路是否同错或只在文本路线异常；③按页面右侧定义选择机制。证据不足时不要猜，保存为“需要更多证据”。</p></div>
<div id="panel"><h2 id="title"></h2><p id="gold"></p><details open><summary>冻结题目与 rubric / Frozen question context and rubric</summary><div id="rubric"></div></details><details id="comparison"><summary>查看模型比较与抽样原因 / Show model comparison and selection reason</summary><p id="selection" class="hint"></p><div id="conditions"></div></details><hr><h3>人工根因判断 / Human root-cause decision</h3><label>机制 / Mechanism <select id="mechanism"></select></label><p id="mechanism-hint" class="hint"></p><label><input id="typical" type="checkbox"> 典型案例 / Useful as a typical case</label><label>简短理由 / Short rationale<textarea id="rationale" maxlength="4000" placeholder="说明从原图、gold 和三路结果中看到的关键依据 / State the key evidence you see."></textarea></label><button id="save-reviewed">保存为已复核并转到下一例 / Save reviewed & next</button> <button id="save-more">保存为需要更多证据 / Needs more evidence</button><p id="message"></p></div></div>
<script>
let state,index=0;
const $=s=>document.querySelector(s), now=()=>new Date().toISOString();
const token=new URLSearchParams(location.search).get('token');
function protectedPath(path){const url=new URL(path,location.origin);url.searchParams.set('token',token||'');return url.pathname+url.search;}
async function api(path,method='GET',body){const r=await fetch(protectedPath(path),{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const j=await r.json();if(!r.ok)throw Error(j.error||'request failed');return j;}
function item(){return state.items[index]}
function complete(entry){return Boolean(entry.human_review)}
function reviewStatus(entry){return entry.human_review?.review_status||'pending'}
function nextIncomplete(after){for(let offset=1;offset<=state.items.length;offset++){const i=(after+offset)%state.items.length;if(!complete(state.items[i]))return i}return after}
function mechanismOptions(){return state.queue.review_form.mechanism_options||[]}
function label(option){return `${option.mechanism_code} — ${option.label_zh} / ${option.label_en}`}
async function load(keep=true,advanceAfter=null){const old=keep&&state?state.items[index]?.queue_item_id:null;state=await api('/api/state');const binding=state.binding||{};$('#binding').textContent=binding.warning||'Private queue and approved image snapshot loaded; exact manifest and displayed image hashes were verified.';$('#binding').className=binding.warning?'warning':'ok';const s=state.summary;$('#summary').textContent=`${s.reviewed_count}/${s.item_count} root causes reviewed; ${s.needs_more_evidence_count} need more evidence; ${s.unreviewed_count} unreviewed`;const select=$('#item');select.replaceChildren();state.items.forEach((entry,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${entry.queue_item_id} · ${entry.question_id} · ${reviewStatus(entry)}`;select.append(o)});if(advanceAfter!==null){index=nextIncomplete(advanceAfter)}else if(old){const found=state.items.findIndex(entry=>entry.queue_item_id===old);if(found>=0)index=found}render();}
function text(parent,value){parent.append(document.createTextNode(value==null?'':String(value)))}
function conditionCard(view){const card=document.createElement('section');card.className='condition';const head=document.createElement('strong');text(head,`${view.condition_id} (${view.input_mode||'mode not recorded'})`);const score=document.createElement('div');score.className=view.matches_gold?'complete':'pending';text(score,view.matches_gold?`预测与 gold 一致（由完整错误书推断）/ Matches gold (inferred from the complete error-book contract): ${view.predicted_score}`:`预测 / Predicted: ${view.predicted_score}; 绝对误差 / Abs. error: ${view.absolute_error}; 置信度 / Confidence: ${view.confidence||'not recorded'}`);card.append(head,score);if(!view.matches_gold){const details=document.createElement('details');const summary=document.createElement('summary');text(summary,'查看该条件的私有模型证据 / Show private model evidence');const evidence=document.createElement('pre');text(evidence,`Extracted evidence:\n${view.extracted_evidence||''}\n\nModel rationale:\n${view.evidence||''}\n\nFlags:\n${(view.flags||[]).join('\n')||'(none)'}`);details.append(summary,evidence);card.append(details)}return card;}
function renderRubric(entry){const context=(state.queue.review_context?.questions||[]).find(question=>question.question_id===entry.question_id);const target=$('#rubric');target.replaceChildren();if(!context){target.textContent='Frozen rubric context is unavailable for this queue item.';return}const pre=document.createElement('pre');text(pre,`Expected answer / 参考答案要点:\n${context.expected||''}\n\nFull-credit rule / 满分规则:\n${context.full_credit_rule||''}\n\nMaterial errors / 关键错误上限:\n${JSON.stringify(context.material_errors||[],null,2)}\n\nScore bands / 分数档位:\n${JSON.stringify(context.score_bands||{},null,2)}\n\nScoring elements / 评分要素:\n${JSON.stringify(context.scoring_elements||[],null,2)}\n\nMultiple-choice rubric / 选择题规则:\n${JSON.stringify(context.rubric||[],null,2)}`);target.append(pre)}
function render(){const entry=item();$('#item').value=index;$('#title').textContent=`${entry.queue_item_id}: ${entry.question_id} · ${reviewStatus(entry)}`;$('#image-title').textContent=`${entry.anonymous_student_id} · ${entry.image.page_suffix}`;$('#image').src=protectedPath('/images/'+encodeURIComponent(entry.image.relative_path));renderRubric(entry);const selection=entry.selection||{};$('#selection').textContent=`选择原因 / Selection: ${selection.reason_zh||''} ${selection.reason_en||''}`;$('#gold').textContent=`人工 gold / Human gold: ${entry.gold_score}`;const conditions=$('#conditions');conditions.replaceChildren(...entry.condition_views.map(conditionCard));$('#comparison').open=false;const select=$('#mechanism');select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='选择一个可审计机制 / Select a mechanism';select.append(empty);mechanismOptions().forEach(option=>{const o=document.createElement('option');o.value=option.mechanism_code;o.textContent=label(option);select.append(o)});const review=entry.human_review||{};select.value=review.mechanism_code||'';$('#typical').checked=Boolean(review.typical_case);$('#typical').disabled=review.review_status==='needs_more_evidence';$('#rationale').value=review.review_rationale||'';updateMechanismHint();}
function updateMechanismHint(){const selected=mechanismOptions().find(option=>option.mechanism_code===$('#mechanism').value);$('#mechanism-hint').textContent=selected?`层级 / Layer: ${selected.error_layer}; 可客观性 / Objectivity: ${selected.objectivity_level}; 后续处置 / Disposition: ${selected.disposition}`:'若当前材料不能支持机制判断，请使用“需要更多证据”。 / Use needs-more-evidence when the material cannot support a mechanism.';}
function payload(status){const entry=item();return {queue_item_id:entry.queue_item_id,review_status:status,mechanism_code:status==='reviewed'?$('#mechanism').value:'',reviewer:$('#reviewer').value.trim(),reviewed_at:now(),review_rationale:$('#rationale').value,typical_case:status==='reviewed'?$('#typical').checked:false};}
async function save(status){const reviewer=$('#reviewer').value.trim();if(!reviewer){alert('请先填写审核人 / Enter reviewer name or initials first.');return}if(status==='reviewed'&&!$('#mechanism').value){alert('请选择机制；若不能判断，请选择“需要更多证据”。 / Select a mechanism, or use needs-more-evidence.');return}if(status==='needs_more_evidence'){$('#typical').checked=false}const before=index;try{await api('/api/review','POST',payload(status));await load(false,before);$('#message').textContent=status==='reviewed'?'已原子保存，并跳到下一例待复核案例。\nSaved atomically and moved to the next pending case.':'已记录为需要更多证据；它不会计入已完成根因，也不会被标为典型案例。\nSaved as needs-more-evidence without asserting a root cause or marking a typical case.'}catch(error){$('#message').textContent=error.message}}
$('#item').onchange=e=>{index=+e.target.value;render()};$('#prev').onclick=()=>{index=Math.max(0,index-1);render()};$('#next').onclick=()=>{index=Math.min(state.items.length-1,index+1);render()};$('#mechanism').onchange=updateMechanismHint;$('#save-reviewed').onclick=()=>save('reviewed');$('#save-more').onclick=()=>save('needs_more_evidence');if(!token){$('#binding').textContent='此页面需要本次本地会话 token / This page requires its single-session local access token.';$('#binding').className='warning'}else{load(false).catch(error=>{$('#binding').textContent=error.message;$('#binding').className='warning';});}
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
