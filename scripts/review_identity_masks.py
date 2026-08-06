"""Prepare and review per-page identity masks on private assembled pages.

The detector proposes only a low-confidence header zone from image geometry. It
never reads text, uses OCR, or approves a mask. A reviewer must draw or adjust
at least one rectangle and approve every page before ``compile`` can create a
new page layout for anonymized rendering. All inputs and outputs are private.
"""

from __future__ import annotations

import argparse
import csv
import json
import secrets
import sys
import threading
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import load_page_layout, sha256_file  # noqa: E402


REVIEW_COLUMNS = (
    "anonymous_id",
    "source_page",
    "local_page",
    "source_image",
    "proposal_kind",
    "proposed_rectangles",
    "review_status",
    "approved_rectangles",
    "reviewer",
    "reviewed_at",
    "notes",
)
REVIEW_STATUSES = {"pending", "approved", "needs_correction"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        summary = initialize_review(
            layout_path=args.layout,
            source_pages_root=args.source_pages_root,
            review_path=args.review,
            private_output_acknowledged=args.private_output_acknowledged,
        )
        print(json.dumps(summary, sort_keys=True))
        return 0
    if args.command == "compile":
        summary = compile_review(
            layout_path=args.layout,
            review_path=args.review,
            output_layout=args.output_layout,
            private_output_acknowledged=args.private_output_acknowledged,
        )
        print(json.dumps(summary, sort_keys=True))
        return 0
    if args.command == "serve":
        _serve(args)
        return 0
    raise ValueError(f"unsupported command: {args.command}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a localhost-only private reviewer for per-page identity masks."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create low-confidence mask proposals")
    init.add_argument("--layout", type=Path, required=True)
    init.add_argument("--source-pages-root", type=Path, required=True)
    init.add_argument("--review", type=Path, required=True)
    init.add_argument("--private-output-acknowledged", action="store_true")

    serve = commands.add_parser("serve", help="serve the local drag-to-mask reviewer")
    serve.add_argument("--layout", type=Path, required=True)
    serve.add_argument("--source-pages-root", type=Path, required=True)
    serve.add_argument("--review", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8764)
    serve.add_argument(
        "--access-token",
        help="Optional URL-safe token for one local reviewer session; generated if omitted.",
    )

    compile_command = commands.add_parser(
        "compile", help="compile fully approved per-page identity masks into a new layout"
    )
    compile_command.add_argument("--layout", type=Path, required=True)
    compile_command.add_argument("--review", type=Path, required=True)
    compile_command.add_argument("--output-layout", type=Path, required=True)
    compile_command.add_argument("--private-output-acknowledged", action="store_true")
    return parser


def initialize_review(
    *,
    layout_path: Path,
    source_pages_root: Path,
    review_path: Path,
    private_output_acknowledged: bool,
) -> dict[str, Any]:
    if not private_output_acknowledged:
        raise ValueError("--private-output-acknowledged is required for identity-mask review")
    if review_path.exists():
        raise FileExistsError(f"review already exists: {review_path}")
    layout = load_page_layout(layout_path)
    page_map = _page_map(layout, source_pages_root)
    rows: list[dict[str, str]] = []
    for source_page, entry in sorted(page_map.items()):
        proposed = _propose_header_zone(entry["image_path"])
        rows.append(
            {
                "anonymous_id": entry["anonymous_id"],
                "source_page": str(source_page),
                "local_page": str(entry["local_page"]),
                "source_image": entry["image_path"].name,
                "proposal_kind": "geometry_only_header_zone_v1",
                "proposed_rectangles": _rectangles_to_json(proposed),
                "review_status": "pending",
                "approved_rectangles": "[]",
                "reviewer": "",
                "reviewed_at": "",
                "notes": "Low-confidence geometry proposal only; verify and adjust manually.",
            }
        )
    review_path.parent.mkdir(parents=True, exist_ok=True)
    _write_rows(review_path, rows)
    return {
        "status": "identity_mask_review_pending",
        "page_count": len(rows),
        "geometry_only_proposal_count": sum(
            bool(_parse_rectangles(row["proposed_rectangles"])) for row in rows
        ),
        "model_run_allowed": False,
    }


def compile_review(
    *,
    layout_path: Path,
    review_path: Path,
    output_layout: Path,
    private_output_acknowledged: bool,
) -> dict[str, Any]:
    if not private_output_acknowledged:
        raise ValueError("--private-output-acknowledged is required for identity-mask compilation")
    if output_layout.exists():
        raise FileExistsError(f"output layout already exists: {output_layout}")
    layout = load_page_layout(layout_path)
    columns, rows = _read_rows(review_path)
    if tuple(columns) != REVIEW_COLUMNS:
        raise ValueError("identity-mask review has unexpected columns")
    expected = {(entry["anonymous_id"], str(source_page)) for source_page, entry in _page_map_from_layout(layout).items()}
    by_pair = {(row["anonymous_id"], row["source_page"]): row for row in rows}
    if set(by_pair) != expected or len(by_pair) != len(rows):
        raise ValueError("identity-mask review rows do not match the page layout")
    for pair in expected:
        row = by_pair[pair]
        rectangles = _parse_rectangles(row["approved_rectangles"])
        if row["review_status"] != "approved" or not rectangles:
            raise ValueError("every page needs an approved non-empty identity mask")
        if not row["reviewer"].strip() or not row["reviewed_at"].strip():
            raise ValueError("every approved identity mask needs reviewer and timestamp")

    compiled = deepcopy(layout)
    for group in compiled["page_groups"]:
        anonymous_id = str(group["anonymous_id"])
        page_masks = list(group.get("page_masks", []))
        for source_page in group["source_pages"]:
            row = by_pair[(anonymous_id, str(source_page))]
            page_masks.append(
                {
                    "source_page": int(source_page),
                    "reason": "identity_mask_review",
                    "rectangles": _parse_rectangles(row["approved_rectangles"]),
                }
            )
        group["page_masks"] = page_masks
    compiled["identity_mask_review"] = {
        "schema_version": 1,
        "status": "all_pages_approved",
        "base_layout_sha256": sha256_file(layout_path),
        "review_sha256": sha256_file(review_path),
        "page_count": len(rows),
    }
    output_layout.parent.mkdir(parents=True, exist_ok=True)
    output_layout.write_text(json.dumps(compiled, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "identity_masks_compiled_pending_render",
        "page_count": len(rows),
        "model_run_allowed": False,
    }


class IdentityMaskReviewStore:
    def __init__(self, *, layout_path: Path, source_pages_root: Path, review_path: Path) -> None:
        self.layout = load_page_layout(layout_path)
        self.source_pages_root = source_pages_root.resolve()
        self.review_path = review_path.resolve()
        self._page_map = _page_map(self.layout, self.source_pages_root)
        columns, rows = _read_rows(self.review_path)
        if tuple(columns) != REVIEW_COLUMNS:
            raise ValueError("identity-mask review has unexpected columns")
        self._rows = {
            (row["anonymous_id"], row["source_page"]): dict(row) for row in rows
        }
        expected = {
            (entry["anonymous_id"], str(source_page))
            for source_page, entry in self._page_map.items()
        }
        if set(self._rows) != expected or len(self._rows) != len(rows):
            raise ValueError("identity-mask review rows do not match page layout")
        self._lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        with self._lock:
            pages = []
            for source_page, entry in sorted(self._page_map.items()):
                row = self._rows[(entry["anonymous_id"], str(source_page))]
                pages.append(
                    {
                        "anonymous_id": entry["anonymous_id"],
                        "source_page": source_page,
                        "local_page": entry["local_page"],
                        "proposal_kind": row["proposal_kind"],
                        "proposed_rectangles": _parse_rectangles(row["proposed_rectangles"]),
                        "review_status": row["review_status"],
                        "approved_rectangles": _parse_rectangles(row["approved_rectangles"]),
                        "reviewer": row["reviewer"],
                        "reviewed_at": row["reviewed_at"],
                        "notes": row["notes"],
                    }
                )
            return {
                "pages": pages,
                "summary": {
                    "page_count": len(pages),
                    "approved": sum(page["review_status"] == "approved" for page in pages),
                    "needs_correction": sum(
                        page["review_status"] == "needs_correction" for page in pages
                    ),
                },
            }

    def save(self, payload: Mapping[str, Any]) -> None:
        anonymous_id = _required_text(payload, "anonymous_id")
        source_page = str(_required_positive_int(payload, "source_page"))
        status = _required_text(payload, "review_status")
        if status not in REVIEW_STATUSES:
            raise ValueError("invalid review status")
        rectangles = _payload_rectangles(payload.get("approved_rectangles"))
        reviewer = _required_text(payload, "reviewer")
        reviewed_at = _required_text(payload, "reviewed_at")
        if status == "approved" and not rectangles:
            raise ValueError("an approved page needs at least one identity rectangle")
        with self._lock:
            row = self._rows.get((anonymous_id, source_page))
            if row is None:
                raise ValueError("unknown anonymous page")
            row.update(
                {
                    "review_status": status,
                    "approved_rectangles": _rectangles_to_json(rectangles),
                    "reviewer": reviewer,
                    "reviewed_at": reviewed_at,
                    "notes": _optional_text(payload, "notes"),
                }
            )
            _write_rows(self.review_path, list(self._rows.values()))

    def image_path(self, source_page: int) -> Path:
        entry = self._page_map.get(source_page)
        if entry is None:
            raise ValueError("unknown source page")
        return entry["image_path"]


def _serve(args: argparse.Namespace) -> None:
    if not 1 <= args.port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    store = IdentityMaskReviewStore(
        layout_path=args.layout,
        source_pages_root=args.source_pages_root,
        review_path=args.review,
    )
    token = args.access_token or secrets.token_urlsafe(32)
    if not token or any(character.isspace() for character in token):
        raise ValueError("--access-token must be non-empty and contain no whitespace")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _handler(store, token))
    print(f"Open this local, single-session URL in a browser (do not share it): http://127.0.0.1:{args.port}/?token={token}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Local identity-mask reviewer stopped.")
    finally:
        server.server_close()


def _handler(store: IdentityMaskReviewStore, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not _token_valid(request, token):
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            if request.path == "/":
                self._bytes(HTTPStatus.OK, _HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if request.path == "/api/state":
                self._json(HTTPStatus.OK, store.state())
                return
            if request.path.startswith("/images/"):
                try:
                    source_page = int(unquote(request.path.removeprefix("/images/")))
                    image = store.image_path(source_page)
                except (ValueError, FileNotFoundError):
                    self._json(HTTPStatus.NOT_FOUND, {"error": "image not found"})
                    return
                self._bytes(HTTPStatus.OK, image.read_bytes(), "image/*")
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not _token_valid(request, token):
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            if request.path != "/api/save":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("request body must be between 1 and 1,000,000 bytes")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                store.save(payload)
            except (ValueError, json.JSONDecodeError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._json(HTTPStatus.OK, {"status": "saved"})

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
            self._bytes(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _page_map(layout: Mapping[str, Any], source_pages_root: Path) -> dict[int, dict[str, Any]]:
    page_map = _page_map_from_layout(layout)
    for source_page, entry in page_map.items():
        matches = list(source_pages_root.glob(f"source-p{source_page:04d}.*"))
        if len(matches) != 1 or not matches[0].is_file():
            raise FileNotFoundError(f"expected exactly one private source image for page {source_page}")
        entry["image_path"] = matches[0].resolve()
    return page_map


def _page_map_from_layout(layout: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    page_map: dict[int, dict[str, Any]] = {}
    for group in layout.get("page_groups", []):
        anonymous_id = str(group["anonymous_id"])
        for local_page, source_page in enumerate(group["source_pages"], start=1):
            page = int(source_page)
            if page in page_map:
                raise ValueError("duplicate source page in layout")
            page_map[page] = {"anonymous_id": anonymous_id, "local_page": local_page}
    if not page_map:
        raise ValueError("page layout contains no source pages")
    return page_map


def _propose_header_zone(path: Path) -> list[dict[str, float]]:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("L")
        image.thumbnail((512, 512))
        width, height = image.size
        pixels = image.load()
        dark = [(x, y) for y in range(height) for x in range(width) if pixels[x, y] < 235]
    if not dark:
        return []
    left = min(point[0] for point in dark)
    right = max(point[0] for point in dark)
    top = min(point[1] for point in dark)
    bottom = max(point[1] for point in dark)
    content_height = max(1, bottom - top + 1)
    header_bottom = min(height - 1, top + max(20, round(content_height * 0.18)))
    padding_x = max(4, round(width * 0.015))
    padding_y = max(4, round(height * 0.01))
    return [
        {
            "left": max(0.0, (left - padding_x) / width),
            "top": max(0.0, (top - padding_y) / height),
            "right": min(1.0, (right + padding_x + 1) / width),
            "bottom": min(1.0, (header_bottom + padding_y + 1) / height),
        }
    ]


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_rows(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (int(item["source_page"]), item["anonymous_id"])):
            writer.writerow({column: row.get(column, "") for column in REVIEW_COLUMNS})


def _parse_rectangles(value: str) -> list[dict[str, float]]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("mask rectangles must be JSON") from error
    if not isinstance(payload, list) or not all(_valid_rectangle(item) for item in payload):
        raise ValueError("mask rectangles must be a list of normalized rectangles")
    return [
        {key: float(item[key]) for key in ("left", "top", "right", "bottom")}
        for item in payload
    ]


def _payload_rectangles(value: object) -> list[dict[str, float]]:
    if not isinstance(value, list) or not all(_valid_rectangle(item) for item in value):
        raise ValueError("approved_rectangles must be a list of normalized rectangles")
    return [
        {key: float(item[key]) for key in ("left", "top", "right", "bottom")}
        for item in value
    ]


def _valid_rectangle(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        left, top, right, bottom = (float(value[key]) for key in ("left", "top", "right", "bottom"))
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= left < right <= 1 and 0 <= top < bottom <= 1


def _rectangles_to_json(rectangles: Sequence[Mapping[str, float]]) -> str:
    return json.dumps(list(rectangles), sort_keys=True, separators=(",", ":"))


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _optional_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _required_positive_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _token_valid(request: Any, token: str) -> bool:
    return parse_qs(request.query).get("token", [""])[0] == token


_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>Identity mask review</title>
<style>body{font-family:system-ui,sans-serif;margin:16px;background:#f7f7f8;color:#1f2937}button,input,textarea{font:inherit;margin:4px}.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.canvas{position:relative;display:inline-block;max-width:100%;margin-top:12px}.canvas img{display:block;max-width:min(100%,1000px);max-height:72vh}.mask{position:absolute;border:2px solid #dc2626;background:#dc262633;pointer-events:none}.note{max-width:1000px;color:#4b5563}</style></head><body>
<h1>Private identity-mask review</h1><p class="note">Local only. Red boxes are suggestions or your draft masks; they are never auto-approved. Drag on the image to add a mask. Every page needs at least one rectangle and explicit approval.</p>
<div class="bar"><button id="prev">Previous</button><button id="next">Next</button><strong id="label"></strong><span id="summary"></span></div>
<div class="bar"><label>Reviewer <input id="reviewer" required></label><button id="suggest">Use suggestions</button><button id="clear">Clear masks</button><button id="approve">Save approved</button><button id="correct">Save needs-correction</button></div>
<textarea id="notes" rows="2" cols="80" placeholder="Private review note"></textarea><div id="canvas" class="canvas"><img id="image" alt="private source page"></div>
<script>const token=new URLSearchParams(location.search).get('token');let state=null,index=0,draft=[];const $=id=>document.getElementById(id);
async function refresh(){state=await fetch('/api/state?token='+encodeURIComponent(token),{cache:'no-store'}).then(r=>r.json());$('summary').textContent=`${state.summary.approved}/${state.summary.page_count} approved`;render();}
function page(){return state.pages[index]};function draw(){const box=$('canvas');box.querySelectorAll('.mask').forEach(x=>x.remove());for(const r of draft){const d=document.createElement('div');d.className='mask';d.style.left=(r.left*100)+'%';d.style.top=(r.top*100)+'%';d.style.width=((r.right-r.left)*100)+'%';d.style.height=((r.bottom-r.top)*100)+'%';box.appendChild(d)}}
function render(){const p=page();$('label').textContent=`${index+1}/${state.pages.length} — ${p.anonymous_id}, local page ${p.local_page} (${p.review_status})`;$('notes').value=p.notes||'';draft=JSON.parse(JSON.stringify(p.approved_rectangles.length?p.approved_rectangles:p.proposed_rectangles));const img=$('image');img.onload=draw;img.src='/images/'+p.source_page+'?token='+encodeURIComponent(token);}
function point(e){const r=$('image').getBoundingClientRect();return{x:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))}}let start=null;$('image').addEventListener('pointerdown',e=>{start=point(e)});$('image').addEventListener('pointerup',e=>{if(!start)return;const end=point(e);if(Math.abs(end.x-start.x)>.005&&Math.abs(end.y-start.y)>.005){draft.push({left:Math.min(start.x,end.x),top:Math.min(start.y,end.y),right:Math.max(start.x,end.x),bottom:Math.max(start.y,end.y)});draw()}start=null});
async function save(status){const p=page();const reviewer=$('reviewer').value.trim();if(!reviewer){alert('Reviewer is required');return}if(status==='approved'&&!draft.length){alert('Approved page needs a mask');return}const response=await fetch('/api/save?token='+encodeURIComponent(token),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({anonymous_id:p.anonymous_id,source_page:p.source_page,review_status:status,approved_rectangles:draft,reviewer,reviewed_at:new Date().toISOString(),notes:$('notes').value})});if(!response.ok){alert((await response.json()).error);return}await refresh();}
$('prev').onclick=()=>{index=(index+state.pages.length-1)%state.pages.length;render()};$('next').onclick=()=>{index=(index+1)%state.pages.length;render()};$('suggest').onclick=()=>{draft=JSON.parse(JSON.stringify(page().proposed_rectangles));draw()};$('clear').onclick=()=>{draft=[];draw()};$('approve').onclick=()=>save('approved');$('correct').onclick=()=>save('needs_correction');refresh();</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
