from __future__ import annotations

"""Local browser reviewer for private anomalous page-count decisions.

Only already-rendered anonymous PNGs are served, only from localhost, and the
only writable target is the private page-scope review CSV.  This tool does not
open raw submissions or call a model.
"""

import argparse
import csv
import json
import secrets
import sys
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import (  # noqa: E402
    expected_review_outputs,
    load_page_layout,
    sha256_file,
)
from benchmark.core.page_scope_workflow import (  # noqa: E402
    PAGE_SCOPE_REVIEW_COLUMNS,
    PAGE_SCOPE_REVIEW_STATUSES,
    PageScopeReviewError,
    validate_page_scope_review,
)


class PageScopeReviewStore:
    """Lock-protected view of anomalous groups and their anonymous images."""

    def __init__(
        self,
        *,
        private_manifest_path: Path,
        expected_pages_per_group: int,
        review_csv_path: Path,
        review_metadata_path: Path,
        layout_path: Path,
        artifact_root: Path,
    ) -> None:
        report = validate_page_scope_review(
            private_manifest_path=private_manifest_path,
            expected_pages_per_group=expected_pages_per_group,
            review_csv_path=review_csv_path,
            metadata_path=review_metadata_path,
        )
        structural_failures = set(report["failed_checks"]) - {
            "all_page_scope_decisions_completed",
            "all_anomalies_approved_include_all",
        }
        if structural_failures:
            raise PageScopeReviewError(
                "page-scope review inputs are inconsistent: "
                + ", ".join(sorted(structural_failures))
            )
        self.review_csv_path = _regular_file(review_csv_path, "page-scope review CSV")
        self.layout_path = _regular_file(layout_path, "page layout")
        self.artifact_root = artifact_root.resolve()
        if not self.artifact_root.is_dir():
            raise FileNotFoundError(self.artifact_root)
        self._lock = threading.Lock()
        self.layout = load_page_layout(self.layout_path)
        self._verify_artifact_binding()
        self._rows = self._load_rows()
        self._groups = self._build_groups()
        self._allowed_images = frozenset(
            image for group in self._groups for image in group["images"]
        )

    def state(self) -> dict[str, Any]:
        with self._lock:
            groups = [
                {
                    "anonymous_id": group["anonymous_id"],
                    "rendered_page_count": group["rendered_page_count"],
                    "expected_pages_per_group": group["expected_pages_per_group"],
                    "scope_review_status": self._rows[group["anonymous_id"]][
                        "scope_review_status"
                    ],
                    "reviewer": self._rows[group["anonymous_id"]]["reviewer"],
                    "reviewed_at": self._rows[group["anonymous_id"]]["reviewed_at"],
                    "notes": self._rows[group["anonymous_id"]]["notes"],
                    "images": list(group["images"]),
                }
                for group in self._groups
            ]
            return {
                "groups": groups,
                "summary": {
                    "group_count": len(groups),
                    "approved_include_all": sum(
                        group["scope_review_status"] == "approved_include_all"
                        for group in groups
                    ),
                    "requires_correction": sum(
                        group["scope_review_status"] == "requires_correction"
                        for group in groups
                    ),
                    "pending": sum(
                        group["scope_review_status"] == "pending" for group in groups
                    ),
                },
            }

    def update(self, payload: Mapping[str, Any]) -> None:
        anonymous_id = _required_text(payload, "anonymous_id")
        status = _required_text(payload, "scope_review_status")
        reviewer = _required_text(payload, "reviewer")
        reviewed_at = _required_text(payload, "reviewed_at")
        notes = _optional_text(payload, "notes")
        if status not in PAGE_SCOPE_REVIEW_STATUSES - {"pending"}:
            raise ValueError("scope_review_status must approve all pages or require correction")
        if status == "requires_correction" and not notes:
            raise ValueError("a correction note is required")
        with self._lock:
            row = self._rows.get(anonymous_id)
            if row is None:
                raise ValueError("unknown anonymous group")
            row.update(
                {
                    "scope_review_status": status,
                    "reviewer": reviewer,
                    "reviewed_at": reviewed_at,
                    "notes": notes,
                }
            )
            self._write_rows()

    def image_path(self, relative_path: str) -> Path:
        if relative_path not in self._allowed_images:
            raise ValueError("requested image is outside the approved page-scope set")
        path = (self.artifact_root / relative_path).resolve()
        try:
            path.relative_to(self.artifact_root)
        except ValueError as error:
            raise ValueError("image path escapes artifact root") from error
        if path.suffix.lower() != ".png" or not path.is_file():
            raise FileNotFoundError(path)
        return path

    def _verify_artifact_binding(self) -> None:
        metadata_path = self.artifact_root / "manifest" / "prep-metadata.json"
        metadata = _load_json_object(metadata_path, "preparation metadata")
        if metadata.get("layout_sha256") != sha256_file(self.layout_path):
            raise ValueError("artifact preparation metadata does not bind to the supplied page layout")
        final_report = _load_json_object(
            self.artifact_root / "manifest" / "final-review-validation.json",
            "final anonymization validation",
        )
        if final_report.get("status") != "ready" or final_report.get("failed_checks"):
            raise ValueError("artifact root is not a fully approved final anonymization output")

    def _load_rows(self) -> dict[str, dict[str, str]]:
        with self.review_csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != PAGE_SCOPE_REVIEW_COLUMNS:
                raise ValueError("page-scope review CSV has unexpected columns")
            rows = [dict(row) for row in reader]
        result: dict[str, dict[str, str]] = {}
        for row in rows:
            anonymous_id = row.get("anonymous_id", "")
            if anonymous_id in result:
                raise ValueError("page-scope review CSV has duplicate anonymous groups")
            result[anonymous_id] = row
        return result

    def _build_groups(self) -> list[dict[str, Any]]:
        outputs = expected_review_outputs(self.layout)
        layout_groups = {
            str(group["anonymous_id"]): group
            for group in self.layout.get("page_groups", [])
            if isinstance(group, Mapping)
        }
        groups: list[dict[str, Any]] = []
        for anonymous_id, row in sorted(self._rows.items()):
            layout_group = layout_groups.get(anonymous_id)
            if layout_group is None:
                raise ValueError("page-scope review group is absent from the rendered page layout")
            source_pages = layout_group.get("source_pages")
            if not isinstance(source_pages, list) or len(source_pages) != int(
                row["rendered_page_count"]
            ):
                raise ValueError("reviewed page count does not match the rendered page layout")
            image_paths = []
            for source_page in source_pages:
                output = outputs.get((anonymous_id, int(source_page)))
                if output is None:
                    raise ValueError("rendered page layout has no deterministic image output")
                image_paths.append(output[0])
            groups.append(
                {
                    "anonymous_id": anonymous_id,
                    "rendered_page_count": int(row["rendered_page_count"]),
                    "expected_pages_per_group": int(row["expected_pages_per_group"]),
                    "images": tuple(image_paths),
                }
            )
        return groups

    def _write_rows(self) -> None:
        ordered = [self._rows[group["anonymous_id"]] for group in self._groups]
        with tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", delete=False, dir=self.review_csv_path.parent
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=PAGE_SCOPE_REVIEW_COLUMNS)
            writer.writeheader()
            writer.writerows(ordered)
        temporary.replace(self.review_csv_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a localhost-only private reviewer for anomalous page-count groups."
    )
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--expected-pages-per-group", type=int, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument(
        "--access-token",
        help="optional single-session localhost token; omit to generate a random token",
    )
    parser.add_argument("--private-output-acknowledged", action="store_true")
    args = parser.parse_args(argv)
    if args.expected_pages_per_group < 1:
        parser.error("--expected-pages-per-group must be positive")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    try:
        store = PageScopeReviewStore(
            private_manifest_path=args.private_manifest,
            expected_pages_per_group=args.expected_pages_per_group,
            review_csv_path=args.review_csv,
            review_metadata_path=args.metadata,
            layout_path=args.layout,
            artifact_root=args.artifact_root,
        )
    except (OSError, ValueError, PageScopeReviewError, json.JSONDecodeError) as error:
        parser.error(str(error))
    access_token = args.access_token or secrets.token_urlsafe(32)
    if len(access_token) < 16:
        parser.error("--access-token must contain at least 16 characters")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _handler_class(store, access_token))
    print(
        "Open this local, single-session URL in a browser (do not share it): "
        f"http://127.0.0.1:{args.port}/?token={access_token}"
    )
    print("This review changes page-scope status only; no model is called.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Local page-scope reviewer stopped.")
    finally:
        server.server_close()
    return 0


def _handler_class(store: PageScopeReviewStore, access_token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._valid_token(request):
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
            elif request.path == "/":
                self._bytes(HTTPStatus.OK, _HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif request.path == "/api/state":
                self._json(HTTPStatus.OK, store.state())
            elif request.path.startswith("/images/"):
                try:
                    path = store.image_path(unquote(request.path.removeprefix("/images/")))
                except (FileNotFoundError, ValueError):
                    self._json(HTTPStatus.NOT_FOUND, {"error": "image not found"})
                else:
                    self._bytes(HTTPStatus.OK, path.read_bytes(), "image/png")
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._valid_token(request):
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            if request.path != "/api/update":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100_000:
                    raise ValueError("request body must be between 1 and 100,000 bytes")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("JSON object required")
                store.update(payload)
            except (ValueError, json.JSONDecodeError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._json(HTTPStatus.OK, {"status": "saved"})

        def _valid_token(self, request: Any) -> bool:
            value = parse_qs(request.query).get("token", [""])[0]
            return isinstance(value, str) and secrets.compare_digest(value, access_token)

        def _json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
            self._bytes(
                status,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _bytes(self, status: HTTPStatus, content: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def _regular_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"{label} must be a regular file: {path}")
    return resolved


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(_regular_file(path, label).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    result = value.strip() if isinstance(value, str) else ""
    if not result:
        raise ValueError(f"{field} is required")
    return result


def _optional_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    return value.strip() if isinstance(value, str) else ""


_HTML = r"""<!doctype html><meta charset="utf-8"><title>Private page-scope review</title>
<style>body{font:14px system-ui,sans-serif;margin:16px;color:#18212f;background:#f7f9fc}#top{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.images{display:grid;gap:12px;margin-top:16px}.images img{max-width:100%;border:1px solid #9aa8bc;background:#fff}.panel{background:#fff;border:1px solid #d4dce8;padding:12px;border-radius:8px;margin-top:14px}.hint{color:#526175}.ok{color:#20724d;font-weight:600}.bad{color:#a21b1b;font-weight:600}button,select,input,textarea{font:inherit;padding:6px 8px}textarea{width:min(100%,640px);min-height:68px}</style>
<body><h1>Private page-scope review</h1><p class="hint">Each group below has an unexpected page count. Inspect all already-anonymized pages: approve only if every rendered page belongs in this submission and should remain in its grading scope. “Requires correction” blocks cohort freeze and records why; it does not delete anything.</p><p id="binding" class="ok">Input binding verified. No model is called.</p><div id="top"><label>Reviewer <input id="reviewer" placeholder="name or initials"></label><span id="summary"></span><select id="group"></select><button id="prev">Previous</button><button id="next">Next</button></div><div class="panel"><h2 id="title"></h2><p id="status"></p><label>Notes (required if correction)<br><textarea id="notes"></textarea></label><p><button id="approve">Approve: retain all pages</button> <button id="correct">Requires correction</button></p><p id="message"></p></div><div id="images" class="images"></div>
<script>let state,index=0;const $=s=>document.querySelector(s),token=new URLSearchParams(location.search).get('token'),now=()=>new Date().toISOString();function path(p){const u=new URL(p,location.origin);u.searchParams.set('token',token||'');return u.pathname+u.search}async function api(p,m='GET',b){const r=await fetch(path(p),{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined}),j=await r.json();if(!r.ok)throw Error(j.error||'request failed');return j}function current(){return state.groups[index]}async function load(keep=true){const old=keep&&state?current().anonymous_id:null;state=await api('/api/state');$('#summary').textContent=`${state.summary.group_count} groups: ${state.summary.approved_include_all} approved, ${state.summary.requires_correction} correction, ${state.summary.pending} pending`;const s=$('#group');s.replaceChildren();state.groups.forEach((g,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${g.anonymous_id} (${g.rendered_page_count} pages)`;s.append(o)});if(old){const i=state.groups.findIndex(g=>g.anonymous_id===old);if(i>=0)index=i}render()}function render(){const g=current();$('#group').value=index;$('#title').textContent=`${g.anonymous_id}: ${g.rendered_page_count} rendered pages (expected ${g.expected_pages_per_group})`;$('#status').textContent='Current decision: '+g.scope_review_status;$('#status').className=g.scope_review_status==='approved_include_all'?'ok':g.scope_review_status==='requires_correction'?'bad':'';$('#notes').value=g.notes||'';const box=$('#images');box.replaceChildren();g.images.forEach((image,i)=>{const figure=document.createElement('figure'),cap=document.createElement('figcaption'),img=document.createElement('img');cap.textContent=`Rendered page ${i+1}`;img.src=path('/images/'+encodeURIComponent(image));img.alt=`anonymous rendered page ${i+1}`;figure.append(cap,img);box.append(figure)})}async function save(status){const reviewer=$('#reviewer').value.trim(),g=current(),notes=$('#notes').value.trim();if(!reviewer){alert('Enter reviewer name or initials.');return}if(status==='requires_correction'&&!notes){alert('Enter a correction note.');return}if(!confirm(status==='approved_include_all'?'Confirm every rendered page belongs in scope?':'Record that this group needs a corrected assembly/layout?'))return;try{await api('/api/update','POST',{anonymous_id:g.anonymous_id,scope_review_status:status,reviewer,reviewed_at:now(),notes});await load();$('#message').textContent='Decision saved.'}catch(e){$('#message').textContent=e.message}}$('#group').onchange=e=>{index=+e.target.value;render()};$('#prev').onclick=()=>{index=Math.max(0,index-1);render()};$('#next').onclick=()=>{index=Math.min(state.groups.length-1,index+1);render()};$('#approve').onclick=()=>save('approved_include_all');$('#correct').onclick=()=>save('requires_correction');if(!token){$('#binding').textContent='This page requires its single-session local access token.';$('#binding').className='bad'}else load(false).catch(e=>{$('#binding').textContent=e.message;$('#binding').className='bad'});</script>"""


if __name__ == "__main__":
    raise SystemExit(main())
