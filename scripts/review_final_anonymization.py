from __future__ import annotations

"""Local-only final approval page for post-redaction anonymous assessment inputs.

This is intentionally separate from ``review_grading_masks.py``.  That tool
collects masking rectangles from the base render; this one shows the *newly
rendered*, post-mask PNGs and records the three final human approvals required
before a direct-multimodal grading packet can be considered.
"""

import argparse
import csv
import json
import secrets
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import (  # noqa: E402
    ANONYMIZATION_REVIEW_COLUMNS,
    expected_review_outputs,
    load_page_layout,
    sha256_file,
    write_review_csv,
)
from benchmark.core.grading_mask_workflow import (  # noqa: E402
    canonical_json_sha256,
    expected_output_paths,
    validate_artifact_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a localhost-only final approval page for already-rendered "
            "anonymous assessment inputs."
        )
    )
    parser.add_argument("--layout", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--prep-metadata", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--data-root", type=Path, default=Path("Data/DSAA3071"))
    parser.add_argument("--week", type=int)
    parser.add_argument("--version")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise ValueError("--port must be between 1 and 65535")

    paths = _resolve_paths(args)
    store = FinalApprovalStore(**paths)
    access_token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), _handler_class(store, access_token=access_token)
    )
    print(
        "Open this local, single-session URL in a browser (do not share it): "
        f"http://127.0.0.1:{args.port}/?token={access_token}"
    )
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Local final-approval reviewer stopped.")
    finally:
        server.server_close()
    return 0


def _resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    direct = {
        "layout_path": args.layout,
        "artifact_root": args.artifact_root,
        "prep_metadata_path": args.prep_metadata,
        "review_path": args.review,
    }
    if args.week is not None or args.version is not None:
        if args.week is None or not args.version:
            raise ValueError("--week and --version must be supplied together")
        if any(value is not None for value in direct.values()):
            raise ValueError("use either --week/--version or explicit path arguments, not both")
        base = args.data_root / f"week{args.week}" / "anonymization"
        artifact_root = base / "artifacts" / args.version
        return {
            "layout_path": base / "layouts" / args.version / "page-layout.json",
            "artifact_root": artifact_root,
            "prep_metadata_path": artifact_root / "manifest" / "prep-metadata.json",
            "review_path": artifact_root / "manifest" / "anonymization_review.csv",
        }
    if any(value is None for value in direct.values()):
        raise ValueError(
            "provide --week and --version, or every explicit private input path"
        )
    return {key: value for key, value in direct.items() if isinstance(value, Path)}


class FinalApprovalStore:
    def __init__(
        self,
        *,
        layout_path: Path,
        artifact_root: Path,
        prep_metadata_path: Path,
        review_path: Path,
    ) -> None:
        self.layout_path = layout_path.resolve()
        self.artifact_root = artifact_root.resolve()
        self.prep_metadata_path = prep_metadata_path.resolve()
        self.review_path = review_path.resolve()
        self._lock = threading.Lock()
        if not self.artifact_root.is_dir():
            raise FileNotFoundError(self.artifact_root)
        self.layout = load_page_layout(self.layout_path)
        self.metadata = _load_json_object(self.prep_metadata_path)
        self._expected_outputs = expected_review_outputs(self.layout)
        self._verify_input_binding()
        self._rows = self._load_and_validate_review_rows()
        self._allowed_image_paths = frozenset(
            image_path for image_path, _pdf_path in self._expected_outputs.values()
        )

    def state(self) -> dict[str, Any]:
        with self._lock:
            pages = []
            for group in self.layout["page_groups"]:
                anonymous_id = str(group["anonymous_id"])
                for source_page in group["source_pages"]:
                    pair = (anonymous_id, int(source_page))
                    row = self._rows[pair]
                    image_path, _pdf_path = self._expected_outputs[pair]
                    statuses = {
                        "privacy": row["privacy_review_status"],
                        "blindness": row["blindness_review_status"],
                        "content": row["answer_content_status"],
                    }
                    pages.append(
                        {
                            "anonymous_id": anonymous_id,
                            "source_page": source_page,
                            "image_path": image_path,
                            "statuses": statuses,
                            "notes": {
                                "privacy": row.get("privacy_notes", ""),
                                "blindness": row.get("blindness_notes", ""),
                                "content": row.get("answer_content_notes", ""),
                            },
                        }
                    )
            approved = sum(
                all(status == "approved" for status in page["statuses"].values())
                for page in pages
            )
            needs_correction = sum(
                any(status == "rejected" for status in page["statuses"].values())
                for page in pages
            )
            return {
                "pages": pages,
                "summary": {
                    "page_count": len(pages),
                    "fully_approved": approved,
                    "needs_correction": needs_correction,
                },
            }

    def approve_all(self, payload: Mapping[str, Any]) -> None:
        pair = _payload_pair(payload)
        reviewer = _required_text(payload, "reviewer")
        reviewed_at = _required_text(payload, "reviewed_at")
        with self._lock:
            row = self._row_for_pair(pair)
            row.update(
                {
                    "privacy_review_status": "approved",
                    "privacy_reviewer": reviewer,
                    "privacy_reviewed_at": reviewed_at,
                    "privacy_notes": "approved in post-render local final review",
                    "blindness_review_status": "approved",
                    "blindness_reviewer": reviewer,
                    "blindness_reviewed_at": reviewed_at,
                    "blindness_notes": "approved in post-render local final review",
                    "answer_content_status": "approved",
                    "answer_content_reviewer": reviewer,
                    "answer_content_reviewed_at": reviewed_at,
                    "answer_content_notes": "approved in post-render local final review",
                }
            )
            self._write_rows()

    def reject(self, payload: Mapping[str, Any]) -> None:
        pair = _payload_pair(payload)
        reviewer = _required_text(payload, "reviewer")
        reviewed_at = _required_text(payload, "reviewed_at")
        note = _required_text(payload, "note")
        with self._lock:
            row = self._row_for_pair(pair)
            message = f"post-render final review needs correction: {note}"
            row.update(
                {
                    "privacy_review_status": "rejected",
                    "privacy_reviewer": reviewer,
                    "privacy_reviewed_at": reviewed_at,
                    "privacy_notes": message,
                    "blindness_review_status": "rejected",
                    "blindness_reviewer": reviewer,
                    "blindness_reviewed_at": reviewed_at,
                    "blindness_notes": message,
                    "answer_content_status": "rejected",
                    "answer_content_reviewer": reviewer,
                    "answer_content_reviewed_at": reviewed_at,
                    "answer_content_notes": message,
                }
            )
            self._write_rows()

    def image_path(self, relative_path: str) -> Path:
        if relative_path not in self._allowed_image_paths:
            raise ValueError("requested resource is not an expected anonymous page PNG")
        path = (self.artifact_root / relative_path).resolve()
        try:
            path.relative_to(self.artifact_root)
        except ValueError as error:
            raise ValueError("image path escapes artifact root") from error
        if path.suffix.lower() != ".png" or not path.is_file():
            raise FileNotFoundError(path)
        return path

    def _verify_input_binding(self) -> None:
        expected_metadata_path = (
            self.artifact_root / "manifest" / "prep-metadata.json"
        ).resolve()
        if self.prep_metadata_path != expected_metadata_path:
            raise ValueError("prep metadata must be inside the matching artifact root")
        if self.metadata.get("schema_version") != 2:
            raise ValueError("final approval requires schema-v2 preparation metadata")
        if self.metadata.get("record_type") != "anonymized_assessment_preparation":
            raise ValueError("prep metadata has an unexpected record_type")
        layout_hash = sha256_file(self.layout_path)
        if self.metadata.get("layout_sha256") != layout_hash:
            raise ValueError("prep metadata does not bind to the supplied page layout")
        render_spec = self.metadata.get("render_spec")
        render_spec_hash = self.metadata.get("render_spec_sha256")
        if not isinstance(render_spec, Mapping) or not isinstance(render_spec_hash, str):
            raise ValueError("schema-v2 prep metadata lacks a render specification")
        if render_spec.get("layout_sha256") != layout_hash:
            raise ValueError("render specification does not bind to the page layout")
        if canonical_json_sha256(render_spec) != render_spec_hash:
            raise ValueError("render specification hash does not match metadata")
        if self.metadata.get("assessment_id") != self.layout.get("assessment_id"):
            raise ValueError("prep metadata assessment_id does not match page layout")

        manifest_path = _metadata_output_path(
            artifact_root=self.artifact_root,
            relative_path=self.metadata.get("artifact_manifest_path"),
            field_name="artifact_manifest_path",
        )
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        if self.metadata.get("artifact_manifest_sha256") != sha256_file(manifest_path):
            raise ValueError("artifact manifest does not match prep metadata")
        artifact_report = validate_artifact_manifest(
            output_root=self.artifact_root,
            layout=self.layout,
            manifest=_load_json_object(manifest_path),
            render_spec_sha256=render_spec_hash,
        )
        if artifact_report["status"] != "ready":
            raise ValueError(
                "prepared artifact validation failed: "
                + ", ".join(artifact_report["failed_checks"])
            )
        expected_files = expected_output_paths(self.layout)
        if not self._expected_outputs or not expected_files:
            raise ValueError("page layout does not define model-facing outputs")

        declared_review_path = _metadata_output_path(
            artifact_root=self.artifact_root,
            relative_path=self.metadata.get("review_path"),
            field_name="review_path",
        )
        if self.review_path != declared_review_path:
            raise ValueError("review CSV does not match the path declared by prep metadata")

    def _load_and_validate_review_rows(self) -> dict[tuple[str, int], dict[str, str]]:
        with self.review_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = tuple(reader.fieldnames or ())
        if tuple(columns) != ANONYMIZATION_REVIEW_COLUMNS:
            raise ValueError("final approval CSV has unexpected columns")
        expected_render = self.metadata.get("render_spec_sha256")
        expected_artifacts = self.metadata.get("artifact_manifest_sha256")
        by_pair: dict[tuple[str, int], dict[str, str]] = {}
        for row in rows:
            try:
                pair = (str(row["anonymous_id"]), int(row["source_page"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("review CSV has an invalid anonymous page pair") from error
            expected = self._expected_outputs.get(pair)
            if pair in by_pair or expected is None:
                raise ValueError("review CSV has duplicate or unexpected page pairs")
            if (
                row.get("render_spec_sha256") != expected_render
                or row.get("artifact_manifest_sha256") != expected_artifacts
                or row.get("output_image") != expected[0]
                or row.get("output_pdf") != expected[1]
            ):
                raise ValueError("review CSV is not bound to the rendered anonymous output")
            by_pair[pair] = dict(row)
        if set(by_pair) != set(self._expected_outputs):
            raise ValueError("review CSV does not cover exactly the rendered anonymous pages")
        return by_pair

    def _row_for_pair(self, pair: tuple[str, int]) -> dict[str, str]:
        row = self._rows.get(pair)
        if row is None:
            raise ValueError("unknown anonymous page")
        return row

    def _write_rows(self) -> None:
        ordered_rows = []
        for group in self.layout["page_groups"]:
            anonymous_id = str(group["anonymous_id"])
            for source_page in group["source_pages"]:
                ordered_rows.append(self._rows[(anonymous_id, int(source_page))])
        write_review_csv(self.review_path, ordered_rows)


def _handler_class(
    store: FinalApprovalStore, *, access_token: str
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._token_is_valid(request):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            if request.path == "/":
                self._send_bytes(HTTPStatus.OK, _HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif request.path == "/api/state":
                self._send_json(HTTPStatus.OK, store.state())
            elif request.path.startswith("/images/"):
                try:
                    image_path = store.image_path(unquote(request.path.removeprefix("/images/")))
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
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("request body must be between 1 and 1,000,000 bytes")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("JSON object required")
                if request.path == "/api/approve-all":
                    store.approve_all(payload)
                elif request.path == "/api/reject":
                    store.reject(payload)
                else:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
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
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _metadata_output_path(
    *, artifact_root: Path, relative_path: object, field_name: str
) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError(f"prep metadata lacks {field_name}")
    path = (artifact_root / relative_path).resolve()
    try:
        path.relative_to(artifact_root)
    except ValueError as error:
        raise ValueError(f"{field_name} escapes artifact root") from error
    return path


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _payload_pair(payload: Mapping[str, Any]) -> tuple[str, int]:
    anonymous_id = _required_text(payload, "anonymous_id")
    try:
        source_page = int(payload.get("source_page"))
    except (TypeError, ValueError) as error:
        raise ValueError("source_page must be a positive integer") from error
    if source_page <= 0:
        raise ValueError("source_page must be a positive integer")
    return anonymous_id, source_page


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    result = value.strip() if isinstance(value, str) else ""
    if not result:
        raise ValueError(f"{key} is required")
    return result


_HTML = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Private final anonymization approval</title>
<style>
body { font:14px system-ui,sans-serif; margin:16px; color:#18212f; background:#f7f9fc; }
#top { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
button,select,input { font:inherit; padding:6px 8px; } button { cursor:pointer; }
#main { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:16px; align-items:start; }
#image { max-width:100%; border:1px solid #9aa8bc; background:white; display:block; }
#panel { background:white; border:1px solid #d4dce8; padding:12px; border-radius:8px; }
.hint { color:#526175; } .warning { color:#8a5600; font-weight:600; } .ok { color:#20724d; font-weight:600; }
.checks { line-height:1.7; } .rejected { color:#a21b1b; font-weight:600; }
@media (max-width:900px) { #main { grid-template-columns:1fr; } }
</style>
<body><h1>Post-render final approval</h1>
<p class="hint">Review the already-redacted anonymous page. Approve only when identity is hidden, human grading evidence is hidden, and required student work remains visible. Each decision applies to the current page only; the reviewer advances to the next undecided page after saving.</p>
<p id="binding" class="ok">Input binding verified.</p>
<div id="top"><label>Reviewer <input id="reviewer" placeholder="name or initials"></label><span id="summary"></span><button id="prev">Previous</button><select id="page"></select><button id="next">Next</button></div>
<div id="main"><div><img id="image" alt="anonymous assessment page"><p class="hint">The displayed page is the exact post-mask PNG bound to the final approval CSV.</p></div>
<div id="panel"><h2 id="title"></h2><div id="checks" class="checks"></div><p class="hint">Approve all three only after checking: (1) no identity, (2) no prior score/tick/comment/total, and (3) no required question or student answer was hidden.</p><button id="approve">Approve all three checks</button><button id="reject">Reject / needs correction</button><p id="message"></p></div></div>
<script>
let state,index=0;
const $=s=>document.querySelector(s), now=()=>new Date().toISOString();
const token=new URLSearchParams(location.search).get('token');
function protectedPath(path){const url=new URL(path,location.origin);url.searchParams.set('token',token||'');return url.pathname+url.search;}
async function api(path,method='GET',body){const r=await fetch(protectedPath(path),{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const j=await r.json();if(!r.ok)throw Error(j.error||'request failed');return j;}
function page(){return state.pages[index]}
function allApproved(p){return Object.values(p.statuses).every(s=>s==='approved')}
function isPending(p){return Object.values(p.statuses).every(s=>s==='pending')}
function nextPendingIndex(after){for(let offset=1;offset<=state.pages.length;offset++){const i=(after+offset)%state.pages.length;if(isPending(state.pages[i]))return i}return after}
async function load(keep=true,focusPendingAfter=null){const old=keep&&state?state.pages[index]?.anonymous_id+'|'+state.pages[index]?.source_page:null;state=await api('/api/state');const remaining=state.summary.page_count-state.summary.fully_approved-state.summary.needs_correction;$('#summary').textContent=`${state.summary.page_count} pages: ${state.summary.fully_approved} approved; ${state.summary.needs_correction} need correction; ${remaining} awaiting decision`;const select=$('#page');select.replaceChildren();state.pages.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${p.anonymous_id} / source page ${p.source_page}`;select.append(o)});if(focusPendingAfter!==null){index=nextPendingIndex(focusPendingAfter)}else if(old){const i=state.pages.findIndex(p=>p.anonymous_id+'|'+p.source_page===old);if(i>=0)index=i}render();}
function render(){const p=page();$('#page').value=index;$('#title').textContent=`${p.anonymous_id}, source page ${p.source_page}`;const checks=$('#checks');checks.replaceChildren();[['privacy','Identity privacy'],['blindness','Blindness to existing grading'],['content','Required content preserved']].forEach(([key,label])=>{const row=document.createElement('div');const status=p.statuses[key];row.textContent=`${label}: ${status}`;if(status==='approved')row.className='ok';if(status==='rejected')row.className='rejected';checks.append(row)});$('#approve').disabled=allApproved(p);$('#image').src=protectedPath('/images/'+encodeURIComponent(p.image_path));}
async function approve(){const reviewer=$('#reviewer').value.trim();if(!reviewer){alert('Enter your reviewer name or initials first.');return}if(!confirm('Approve identity privacy, blindness, and content preservation for this page?'))return;const p=page(),completedIndex=index;try{await api('/api/approve-all','POST',{anonymous_id:p.anonymous_id,source_page:p.source_page,reviewer,reviewed_at:now()});await load(false,completedIndex);$('#message').textContent='All three approvals saved. Moved to the next undecided page.'}catch(e){$('#message').textContent=e.message}}
async function reject(){const reviewer=$('#reviewer').value.trim();if(!reviewer){alert('Enter your reviewer name or initials first.');return}const note=prompt('What must be corrected (identity leak, remaining grading mark, or hidden content)?')||'';if(!note.trim()){alert('A correction note is required.');return}const p=page(),completedIndex=index;try{await api('/api/reject','POST',{anonymous_id:p.anonymous_id,source_page:p.source_page,reviewer,reviewed_at:now(),note});await load(false,completedIndex);$('#message').textContent='Correction requirement saved. Moved to the next undecided page.'}catch(e){$('#message').textContent=e.message}}
$('#page').onchange=e=>{index=+e.target.value;render()};$('#prev').onclick=()=>{index=Math.max(0,index-1);render()};$('#next').onclick=()=>{index=Math.min(state.pages.length-1,index+1);render()};$('#approve').onclick=approve;$('#reject').onclick=reject;if(!token){$('#binding').textContent='This page requires its single-session local access token.';$('#binding').className='warning';}else{load(false).catch(e=>{$('#binding').textContent=e.message;$('#binding').className='warning';});}
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
