from __future__ import annotations

"""Local-only reviewer for private grading-mark mask candidates.

The server binds to 127.0.0.1 only. It is intentionally a local reviewer aid,
not a model service and not a replacement for the final three safety approvals.
"""

import argparse
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

from benchmark.core.anonymization import load_page_layout
from benchmark.core.grading_mask_workflow import (
    MASK_CANDIDATE_DECISION_COLUMNS,
    PAGE_SWEEP_COLUMNS,
    REVIEW_STATUSES,
    SWEEP_STATUSES,
    canonical_json_sha256,
    expected_output_paths,
    load_csv_rows,
    parse_rectangles,
    rectangles_to_json,
    sha256_file,
    validate_artifact_manifest,
    write_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a localhost-only private reviewer for grading-mark masks."
    )
    parser.add_argument("--layout", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument(
        "--prep-metadata",
        type=Path,
        help="matching manifest/prep-metadata.json emitted by preparation",
    )
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--candidate-decisions", type=Path)
    parser.add_argument("--page-sweeps", type=Path)
    parser.add_argument("--data-root", type=Path, default=Path("Data/DSAA3071"))
    parser.add_argument("--week", type=int)
    parser.add_argument("--version")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    paths = _resolve_paths(args)
    store = ReviewStore(
        layout_path=paths["layout"],
        artifact_root=paths["artifact_root"],
        prep_metadata_path=paths["prep_metadata"],
        candidate_manifest_path=paths["candidate_manifest"],
        candidate_decisions_path=paths["candidate_decisions"],
        page_sweeps_path=paths["page_sweeps"],
    )
    access_token = secrets.token_urlsafe(32)
    handler = _handler_class(store, access_token=access_token)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(
        "Open this local, single-session URL in a browser (do not share it): "
        f"http://127.0.0.1:{args.port}/?token={access_token}"
    )
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Local mask reviewer stopped.")
    finally:
        server.server_close()
    return 0


def _resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    direct = {
        "layout": args.layout,
        "artifact_root": args.artifact_root,
        "prep_metadata": args.prep_metadata,
        "candidate_manifest": args.candidate_manifest,
        "candidate_decisions": args.candidate_decisions,
        "page_sweeps": args.page_sweeps,
    }
    if args.week is not None or args.version is not None:
        if args.week is None or not args.version:
            raise ValueError("--week and --version must be supplied together")
        if any(value is not None for value in direct.values()):
            raise ValueError("use either --week/--version or explicit path arguments, not both")
        base = args.data_root / f"week{args.week}" / "anonymization"
        review = base / "mask-review" / args.version
        return {
            "layout": base / "layouts" / args.version / "page-layout.json",
            "artifact_root": base / "artifacts" / args.version,
            "prep_metadata": base / "artifacts" / args.version / "manifest" / "prep-metadata.json",
            "candidate_manifest": review / "candidate-manifest.json",
            "candidate_decisions": review / "candidate-decisions.csv",
            "page_sweeps": review / "page-sweeps.csv",
        }
    if any(value is None for value in direct.values()):
        raise ValueError(
            "provide --week and --version, or provide all explicit private path arguments "
            "including --prep-metadata"
        )
    return {key: value for key, value in direct.items() if isinstance(value, Path)}


class ReviewStore:
    def __init__(
        self,
        *,
        layout_path: Path,
        artifact_root: Path,
        prep_metadata_path: Path,
        candidate_manifest_path: Path,
        candidate_decisions_path: Path,
        page_sweeps_path: Path,
    ) -> None:
        self.layout_path = layout_path.resolve()
        self.artifact_root = artifact_root.resolve()
        self.prep_metadata_path = prep_metadata_path.resolve()
        self.candidate_manifest_path = candidate_manifest_path.resolve()
        self.candidate_decisions_path = candidate_decisions_path.resolve()
        self.page_sweeps_path = page_sweeps_path.resolve()
        self._lock = threading.Lock()
        if not self.artifact_root.is_dir():
            raise FileNotFoundError(self.artifact_root)
        self.layout = load_page_layout(self.layout_path)
        self.prep_metadata = _load_json_object(self.prep_metadata_path)
        self.manifest = _load_json_object(self.candidate_manifest_path)
        self.candidate_columns, self.decision_rows = load_csv_rows(self.candidate_decisions_path)
        self.sweep_columns, self.sweep_rows = load_csv_rows(self.page_sweeps_path)
        if tuple(self.candidate_columns) != MASK_CANDIDATE_DECISION_COLUMNS:
            raise ValueError("candidate decision CSV has unexpected columns")
        if tuple(self.sweep_columns) != PAGE_SWEEP_COLUMNS:
            raise ValueError("page sweep CSV has unexpected columns")
        self._binding = self._verify_input_binding()
        self._pages = self._build_pages()
        expected_images = {
            path
            for path in expected_output_paths(self.layout)
            if path.startswith("anonymized_pages/") and path.endswith(".png")
        }
        page_images = {page["image_path"] for page in self._pages}
        if page_images != expected_images:
            raise ValueError("page layout does not map to the expected anonymous page PNGs")
        self._allowed_image_paths = frozenset(expected_images)

    def state(self) -> dict[str, Any]:
        with self._lock:
            decisions = {row["candidate_id"]: dict(row) for row in self.decision_rows}
            sweeps = {
                (row["anonymous_id"], row["source_page"]): dict(row)
                for row in self.sweep_rows
            }
            candidates_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for candidate in self.manifest.get("candidates", []):
                if not isinstance(candidate, dict):
                    continue
                pair = (str(candidate["anonymous_id"]), str(candidate["source_page"]))
                candidate_copy = dict(candidate)
                candidate_copy["decision"] = decisions.get(str(candidate["candidate_id"]), {})
                candidates_by_pair.setdefault(pair, []).append(candidate_copy)
            pages = []
            for page in self._pages:
                pair = (page["anonymous_id"], str(page["source_page"]))
                page_copy = dict(page)
                page_copy["candidates"] = candidates_by_pair.get(pair, [])
                page_copy["sweep"] = sweeps.get(pair, {})
                pages.append(page_copy)
            return {
                "pages": pages,
                "binding": dict(self._binding),
                "summary": {
                    "page_count": len(pages),
                    "candidate_count": sum(len(page["candidates"]) for page in pages),
                    "sweeps_completed": sum(
                        1
                        for page in pages
                        if page["sweep"].get("sweep_status") == "completed"
                    ),
                    "candidates_resolved": sum(
                        1
                        for page in pages
                        for candidate in page["candidates"]
                        if candidate["decision"].get("decision_status")
                        in {"accepted", "rejected", "adjusted"}
                    ),
                },
            }

    def update_decision(self, payload: Mapping[str, Any]) -> None:
        candidate_id = _require_text(payload, "candidate_id")
        status = _require_text(payload, "decision_status")
        if status not in REVIEW_STATUSES:
            raise ValueError("invalid candidate decision status")
        final_rectangles = _payload_rectangles(payload.get("final_rectangles"))
        with self._lock:
            row = _find_row(self.decision_rows, "candidate_id", candidate_id)
            if row is None:
                raise ValueError("unknown candidate_id")
            row["decision_status"] = status
            row["final_rectangles"] = rectangles_to_json(final_rectangles)
            row["reviewer"] = _optional_text(payload, "reviewer")
            row["reviewed_at"] = _optional_text(payload, "reviewed_at")
            row["notes"] = _optional_text(payload, "notes")
            self._write_decisions()

    def update_sweep(self, payload: Mapping[str, Any]) -> None:
        anonymous_id = _require_text(payload, "anonymous_id")
        source_page = str(_require_positive_int(payload, "source_page"))
        status = _require_text(payload, "sweep_status")
        if status not in SWEEP_STATUSES:
            raise ValueError("invalid page sweep status")
        added_rectangles = _payload_rectangles(payload.get("added_rectangles"))
        with self._lock:
            row = next(
                (
                    item
                    for item in self.sweep_rows
                    if item["anonymous_id"] == anonymous_id
                    and item["source_page"] == source_page
                ),
                None,
            )
            if row is None:
                raise ValueError("unknown page sweep")
            row["sweep_status"] = status
            row["reviewer"] = _optional_text(payload, "reviewer")
            row["reviewed_at"] = _optional_text(payload, "reviewed_at")
            row["added_rectangles"] = rectangles_to_json(added_rectangles)
            row["notes"] = _optional_text(payload, "notes")
            self._write_sweeps()

    def image_path(self, relative_path: str) -> Path:
        if relative_path not in self._allowed_image_paths:
            raise ValueError("requested resource is not an expected anonymous page PNG")
        candidate = (self.artifact_root / relative_path).resolve()
        try:
            candidate.relative_to(self.artifact_root)
        except ValueError as error:
            raise ValueError("image path escapes artifact root") from error
        if candidate.suffix.lower() != ".png" or not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate

    def _verify_input_binding(self) -> dict[str, Any]:
        """Bind this reviewer to one layout, candidate pack, and prepared artifact set.

        The candidate-review phase legitimately uses old schema-v1 identity-only
        artifacts.  They can be inspected here, but the returned warning makes
        clear that a later schema-v2 render is still required before any model
        receives pages.
        """

        expected_metadata_path = (
            self.artifact_root / "manifest" / "prep-metadata.json"
        ).resolve()
        if self.prep_metadata_path != expected_metadata_path:
            raise ValueError(
                "prep metadata must be the manifest/prep-metadata.json under the "
                "same --artifact-root"
            )

        metadata_schema = self.prep_metadata.get("schema_version")
        if metadata_schema not in {1, 2}:
            raise ValueError("prep metadata must use schema_version 1 or 2")
        if self.prep_metadata.get("record_type") != "anonymized_assessment_preparation":
            raise ValueError("prep metadata has an unexpected record_type")
        if self.manifest.get("schema_version") != 1:
            raise ValueError("candidate manifest must use schema_version=1")
        if self.manifest.get("record_type") != "grading_mark_mask_candidate_manifest":
            raise ValueError("candidate manifest has an unexpected record_type")

        layout_sha256 = sha256_file(self.layout_path)
        if self.prep_metadata.get("layout_sha256") != layout_sha256:
            raise ValueError("prep metadata does not bind to the supplied page layout")
        if self.manifest.get("layout_sha256") != layout_sha256:
            raise ValueError("candidate manifest does not bind to the supplied page layout")

        assessment_id = self.layout.get("assessment_id")
        if not isinstance(assessment_id, str) or not assessment_id:
            raise ValueError("page layout requires a non-empty assessment_id")
        if self.prep_metadata.get("assessment_id") != assessment_id:
            raise ValueError("prep metadata assessment_id does not match the page layout")
        if self.manifest.get("assessment_id") != assessment_id:
            raise ValueError("candidate manifest assessment_id does not match the page layout")

        if metadata_schema == 1:
            return {
                "status": "legacy_base_artifacts_verified",
                "metadata_schema_version": 1,
                "warning": (
                    "Legacy schema-v1 base artifacts: layout and candidate pack are "
                    "bound, but output artifact hashes are unavailable. Rerender with "
                    "schema-v2 preparation before any model run."
                ),
            }

        render_spec = self.prep_metadata.get("render_spec")
        render_spec_sha256 = self.prep_metadata.get("render_spec_sha256")
        if not isinstance(render_spec, Mapping) or not isinstance(render_spec_sha256, str):
            raise ValueError("schema-v2 prep metadata lacks a render specification")
        if render_spec.get("layout_sha256") != layout_sha256:
            raise ValueError("schema-v2 render specification does not bind to the page layout")
        if canonical_json_sha256(render_spec) != render_spec_sha256:
            raise ValueError("schema-v2 render specification hash does not match metadata")

        artifact_relative = self.prep_metadata.get("artifact_manifest_path")
        if not isinstance(artifact_relative, str) or not artifact_relative:
            raise ValueError("schema-v2 prep metadata lacks artifact_manifest_path")
        artifact_path = (self.artifact_root / artifact_relative).resolve()
        try:
            artifact_path.relative_to(self.artifact_root)
        except ValueError as error:
            raise ValueError("artifact manifest path escapes artifact root") from error
        if not artifact_path.is_file():
            raise FileNotFoundError(artifact_path)
        if self.prep_metadata.get("artifact_manifest_sha256") != sha256_file(artifact_path):
            raise ValueError("artifact manifest does not match schema-v2 prep metadata")

        artifact_report = validate_artifact_manifest(
            output_root=self.artifact_root,
            layout=self.layout,
            manifest=_load_json_object(artifact_path),
            render_spec_sha256=render_spec_sha256,
        )
        if artifact_report["status"] != "ready":
            failed = ", ".join(artifact_report["failed_checks"])
            raise ValueError(f"prepared artifact validation failed: {failed}")
        return {
            "status": "artifact_set_verified",
            "metadata_schema_version": 2,
            "warning": "",
        }

    def _build_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        for group in self.layout.get("page_groups", []):
            anonymous_id = str(group["anonymous_id"])
            for local_page, source_page in enumerate(group["source_pages"], start=1):
                pages.append(
                    {
                        "anonymous_id": anonymous_id,
                        "source_page": source_page,
                        "image_path": (
                            f"anonymized_pages/{anonymous_id}/{anonymous_id}-p{local_page:02d}.png"
                        ),
                    }
                )
        return pages

    def _write_decisions(self) -> None:
        write_csv(
            self.candidate_decisions_path,
            columns=MASK_CANDIDATE_DECISION_COLUMNS,
            rows=self.decision_rows,
        )

    def _write_sweeps(self) -> None:
        write_csv(
            self.page_sweeps_path,
            columns=PAGE_SWEEP_COLUMNS,
            rows=self.sweep_rows,
        )


def _handler_class(
    store: ReviewStore, *, access_token: str
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._token_is_valid(request):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            path = request.path
            if path == "/":
                self._send_bytes(HTTPStatus.OK, _HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._send_json(HTTPStatus.OK, store.state())
            elif path.startswith("/images/"):
                try:
                    image_path = store.image_path(unquote(path.removeprefix("/images/")))
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
            path = request.path
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("request body must be between 1 and 1,000,000 bytes")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                if path == "/api/decision":
                    store.update_decision(payload)
                elif path == "/api/sweep":
                    store.update_sweep(payload)
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


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _find_row(
    rows: list[dict[str, str]], key: str, value: str
) -> dict[str, str] | None:
    return next((row for row in rows if row.get(key) == value), None)


def _payload_rectangles(value: object) -> list[dict[str, float]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("rectangles must be a JSON array")
    return parse_rectangles(json.dumps(value))


def _require_text(payload: Mapping[str, Any], key: str) -> str:
    value = _optional_text(payload, key)
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _require_positive_int(payload: Mapping[str, Any], key: str) -> int:
    try:
        value = int(payload.get(key))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


_HTML = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Private grading-mark review</title>
<style>
body { font: 14px system-ui, sans-serif; margin: 16px; color: #18212f; background: #f7f9fc; }
#top { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
button, select, input { font: inherit; padding:6px 8px; }
button { cursor:pointer; } #canvas { max-width:100%; border:1px solid #9aa8bc; background:white; touch-action:none; }
#main { display:grid; grid-template-columns:minmax(0, 1fr) 340px; gap:16px; align-items:start; }
#panel { background:white; border:1px solid #d4dce8; padding:12px; border-radius:8px; }
.candidate { border-top:1px solid #e3e8f0; padding:8px 0; } .candidate:first-child { border-top:0; }
.status { font-weight:600; } .hint { color:#526175; } .warning { color:#8a5600; font-weight:600; } .ok { color:#20724d; }
@media (max-width:900px) { #main { grid-template-columns:1fr; } }
</style>
<body><h1>Private grading-mark review</h1>
<p class="hint">Local only. Candidate boxes are suggestions, not masks. Inspect the full page, draw any missed grading evidence, then complete the page sweep.</p>
<p id="binding"></p>
<div id="top"><label>Reviewer <input id="reviewer" placeholder="name or initials"></label><span id="summary"></span><button id="prev">Previous</button><select id="page"></select><button id="next">Next</button></div>
<div id="main"><div><canvas id="canvas"></canvas><p class="hint">Drag on the page to add as many manual grading-mark rectangles as needed. Purple dashed boxes are not saved until you save the page sweep.</p></div>
<div id="panel"><h2 id="title"></h2><div id="candidates"></div><hr><h3>Full-page sweep</h3><p class="hint">This is mandatory even when there are zero candidates. It must catch grayscale marks the detector cannot distinguish from student writing.</p><div id="manual"></div><button id="undo" disabled>Undo last unsaved box</button><button id="clear" disabled>Clear unsaved boxes</button><br><br><button id="complete">Save and complete sweep</button><button id="pending">Save as pending</button><p id="message"></p></div></div>
<script>
let state, index=0, image, draft=null, draftStart=null;
const canvas=document.querySelector('#canvas'), ctx=canvas.getContext('2d');
const pageDrafts=new Map();
const $=s=>document.querySelector(s); const now=()=>new Date().toISOString();
const accessToken=new URLSearchParams(window.location.search).get('token');
function protectedPath(path) { const url=new URL(path, window.location.origin); url.searchParams.set('token',accessToken||''); return url.pathname+url.search; }
async function api(path, method='GET', body) { const r=await fetch(protectedPath(path),{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined}); const j=await r.json(); if(!r.ok)throw Error(j.error||'request failed'); return j; }
function safeRectangles(value) { return Array.isArray(value) ? value.filter(r=>r && ['left','top','right','bottom'].every(k=>Number.isFinite(Number(r[k]))) && Number(r.left)>=0 && Number(r.top)>=0 && Number(r.right)>Number(r.left) && Number(r.bottom)>Number(r.top) && Number(r.right)<=1 && Number(r.bottom)<=1) : []; }
function rects(value) { try { return safeRectangles(value?JSON.parse(value):[]); } catch { return []; } }
function page(){return state.pages[index]}
function pageKey(p=page()){return `${p.anonymous_id}|${p.source_page}`}
function unsavedRects(p=page()){return pageDrafts.get(pageKey(p))||[]}
function setUnsaved(rectangles,p=page()){const clean=safeRectangles(rectangles);if(clean.length)pageDrafts.set(pageKey(p),clean);else pageDrafts.delete(pageKey(p));}
function updateManualSummary(){const saved=rects(page().sweep?.added_rectangles).length, unsaved=unsavedRects().length;$('#manual').textContent=`Manual rectangles: ${saved} saved; ${unsaved} unsaved`;$('#undo').disabled=unsaved===0;$('#clear').disabled=unsaved===0;}
function candidateRectangles(candidate) { const decision=candidate.decision||{}; return decision.decision_status==='adjusted' ? rects(decision.final_rectangles) : safeRectangles(candidate.rectangles); }
async function load(keep=true){ const old=keep&&state?state.pages[index]?.anonymous_id+'|'+state.pages[index]?.source_page:null; state=await api('/api/state'); const binding=state.binding||{}; $('#binding').textContent=binding.warning||'Input binding verified: layout, candidate pack, and rendered artifact manifest belong together.'; $('#binding').className=binding.warning?'warning':'ok'; $('#summary').textContent=`${state.summary.sweeps_completed}/${state.summary.page_count} page sweeps complete; ${state.summary.candidates_resolved}/${state.summary.candidate_count} candidates resolved`; const selector=$('#page'); selector.replaceChildren(); state.pages.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${p.anonymous_id} / source page ${p.source_page}`;selector.append(o)}); if(old){const i=state.pages.findIndex(p=>p.anonymous_id+'|'+p.source_page===old);if(i>=0)index=i} render(); }
function draw(){ const p=page(); ctx.clearRect(0,0,canvas.width,canvas.height); ctx.drawImage(image,0,0); const stroke=(r,color,label,dashed=false)=>{ctx.save();ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=3;if(dashed)ctx.setLineDash([8,5]);ctx.strokeRect(r.left*canvas.width,r.top*canvas.height,(r.right-r.left)*canvas.width,(r.bottom-r.top)*canvas.height);if(label)ctx.fillText(label,r.left*canvas.width+3,Math.max(12,r.top*canvas.height+12));ctx.restore();}; p.candidates.forEach(c=>{const status=c.decision?.decision_status||'pending';const style=status==='accepted'?['#20724d',false]:status==='adjusted'?['#7b2cbf',false]:status==='rejected'?['#7b8798',true]:['#ff7a00',false];candidateRectangles(c).forEach(r=>stroke(r,style[0],`${c.candidate_id} (${status})`,style[1]));}); rects(p.sweep?.added_rectangles).forEach((r,i)=>stroke(r,'#006bd6','saved '+(i+1))); unsavedRects().forEach((r,i)=>stroke(r,'#b000b5','unsaved '+(i+1),true)); if(draft)stroke(draft,'#b000b5','drawing',true); }
function candidateCard(candidate) { const card=document.createElement('div');card.className='candidate'; const heading=document.createElement('div');const id=document.createElement('b');id.textContent=String(candidate.candidate_id||'candidate'); const status=document.createElement('span');status.className='status';status.textContent=' '+String(candidate.decision?.decision_status||'pending');heading.append(id,status);const rationale=document.createElement('div');rationale.className='hint';rationale.textContent=String(candidate.rationale||'');card.append(heading,rationale);[['accept','Accept'],['reject','Reject'],['adjust','Use latest unsaved box']].forEach(([action,label])=>{const button=document.createElement('button');button.textContent=label;button.onclick=()=>saveCandidate(candidate,action);card.append(button);card.append(document.createTextNode(' '));});return card; }
function render(){ draft=null;draftStart=null;const p=page(); $('#page').value=index; $('#title').textContent=`${p.anonymous_id}, source page ${p.source_page}`; const candidates=$('#candidates');candidates.replaceChildren(...p.candidates.map(candidateCard)); updateManualSummary(); const nextImage=new Image(); image=nextImage; nextImage.onload=()=>{if(image!==nextImage)return;canvas.width=nextImage.naturalWidth;canvas.height=nextImage.naturalHeight;draw()}; nextImage.onerror=()=>{if(image===nextImage){$('#message').textContent='Could not load this anonymous page. Try the page again or tell Codex.';}}; nextImage.src=protectedPath('/images/'+encodeURIComponent(p.image_path)); }
async function saveCandidate(c, action){ const reviewer=$('#reviewer').value.trim(); if(!reviewer){alert('Enter your reviewer name or initials first.');return} let notes='', final=[], remaining=null; if(action==='reject'){notes=prompt('Why is this not a grading mark?')||'';if(!notes.trim()){alert('A rejection needs a short note.');return}} if(action==='adjust'){const pending=unsavedRects();if(!pending.length){alert('Draw a replacement box first. The newest unsaved box will be used.');return}final=[pending[pending.length-1]];remaining=pending.slice(0,-1)} const status=action==='accept'?'accepted':action==='reject'?'rejected':'adjusted'; try{await api('/api/decision','POST',{candidate_id:c.candidate_id,decision_status:status,final_rectangles:final,reviewer,reviewed_at:now(),notes});if(remaining)setUnsaved(remaining);$('#message').textContent='Candidate saved.';await load()}catch(e){$('#message').textContent=e.message} }
async function saveSweep(status){ const reviewer=$('#reviewer').value.trim(); if(status==='completed'&&!reviewer){alert('Enter your reviewer name or initials first.');return} const p=page(), pending=unsavedRects(), added=[...rects(p.sweep?.added_rectangles),...pending]; try{await api('/api/sweep','POST',{anonymous_id:p.anonymous_id,source_page:p.source_page,sweep_status:status,reviewer,reviewed_at:now(),added_rectangles:added,notes:''});setUnsaved([]);$('#message').textContent='Page sweep saved.';await load()}catch(e){$('#message').textContent=e.message} }
function canvasPoint(e){const r=canvas.getBoundingClientRect();return {x:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))}}
function finishDraft(){if(!draft)return;const finalized=safeRectangles([draft]);draft=null;draftStart=null;if(finalized.length)setUnsaved([...unsavedRects(),finalized[0]]);updateManualSummary();draw();}
canvas.addEventListener('pointerdown',e=>{const point=canvasPoint(e);draftStart=point;draft={left:point.x,top:point.y,right:point.x,bottom:point.y};canvas.setPointerCapture(e.pointerId)});canvas.addEventListener('pointermove',e=>{if(!draftStart)return;const point=canvasPoint(e);draft={left:Math.min(draftStart.x,point.x),top:Math.min(draftStart.y,point.y),right:Math.max(draftStart.x,point.x),bottom:Math.max(draftStart.y,point.y)};draw()});canvas.addEventListener('pointerup',finishDraft);canvas.addEventListener('pointercancel',()=>{draft=null;draftStart=null;draw()});
$('#page').onchange=e=>{index=+e.target.value;render()}; $('#prev').onclick=()=>{index=Math.max(0,index-1);render()}; $('#next').onclick=()=>{index=Math.min(state.pages.length-1,index+1);render()}; $('#undo').onclick=()=>{const pending=unsavedRects();setUnsaved(pending.slice(0,-1));updateManualSummary();draw()};$('#clear').onclick=()=>{setUnsaved([]);updateManualSummary();draw()};$('#complete').onclick=()=>saveSweep('completed');$('#pending').onclick=()=>saveSweep('pending');if(!accessToken){$('#binding').textContent='This page requires its single-session local access token.';$('#binding').className='warning';}else{load(false).catch(e=>{$('#binding').textContent=e.message;$('#binding').className='warning';});}
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
