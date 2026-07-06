#!/usr/bin/env python3
"""Pull homework submissions from Zulip DMs into a local folder.

Reads the grading bot's zuliprc, fetches private messages it received in a
window, downloads image/PDF attachments into ``weekN/submissions/`` using the
filename convention expected by ``/grade-homework``:

    weekN/submissions/<student_id>_<message_id>_<n>_<original>.<ext>

Maintains ``weekN/zulip-pull.json`` so re-runs are idempotent (uses the
maximum message ID already fetched as the anchor for the next call).

Unknown senders (not in the roster) are written to ``weekN/submissions/_unknown/``
and reported in the JSON summary so the caller can prompt the user to update
the roster.

Outputs a single JSON line on stdout summarizing the run. Diagnostic lines
go to stderr.
"""

from __future__ import annotations

import argparse
import configparser
import csv
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import zulip


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".pdf", ".heic", ".webp", ".gif"}
ATTACHMENT_RE = re.compile(r"\[(?P<label>[^\]]*)\]\((?P<url>/user_uploads/[^)\s]+)\)")
FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def slug_filename(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = FILENAME_SAFE_RE.sub("_", s).strip("._")
    return s or "file"


def parse_iso(s: str) -> int:
    """Return Unix timestamp (seconds) for an ISO 8601 string."""
    dt = datetime.fromisoformat(s)
    return int(dt.timestamp())


def load_roster(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    roster: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("zulip_email") or "").strip().lower()
            sid = (row.get("student_id") or "").strip()
            name = (row.get("student_name") or "").strip()
            if email and sid:
                roster[email] = {"student_id": sid, "student_name": name}
    return roster


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"last_pull_at": None, "last_message_id": 0, "fetched_message_ids": []}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def read_zuliprc_site(path: Path) -> tuple[str, str, str]:
    """Return (bot_email, api_key, site) from a zuliprc INI file."""
    cfg = configparser.ConfigParser()
    cfg.read(path)
    api = cfg["api"]
    return api["email"], api["key"], api["site"].rstrip("/")


def extract_attachment_urls(content: str) -> list[tuple[str, str]]:
    """Return [(label, url), ...] for /user_uploads/... attachments in message markdown."""
    return [(m.group("label"), m.group("url")) for m in ATTACHMENT_RE.finditer(content)]


def looks_like_attachment(label: str, url: str) -> bool:
    name = label or url.rsplit("/", 1)[-1]
    ext = Path(name).suffix.lower()
    return ext in IMAGE_EXTS


def download_attachment(site: str, url_path: str, bot_email: str, api_key: str, dest: Path) -> None:
    full_url = site + url_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(full_url, auth=(bot_email, api_key), stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                f.write(chunk)


def fetch_all_dms(client: zulip.Client, anchor: int, after_ts: int | None, until_ts: int | None) -> list[dict[str, Any]]:
    """Page through private messages newer than ``anchor`` (message id)."""
    out: list[dict[str, Any]] = []
    cur_anchor = anchor
    page_size = 1000
    while True:
        result = client.get_messages({
            "anchor": cur_anchor,
            "num_before": 0,
            "num_after": page_size,
            "narrow": [{"operator": "is", "operand": "private"}],
            "apply_markdown": False,
        })
        if result.get("result") != "success":
            raise RuntimeError(f"get_messages failed: {result.get('msg', '?')}")
        msgs = result.get("messages", [])
        new = [m for m in msgs if m["id"] > anchor]
        if after_ts is not None:
            new = [m for m in new if m.get("timestamp", 0) >= after_ts]
        if until_ts is not None:
            new = [m for m in new if m.get("timestamp", 0) <= until_ts]
        out.extend(new)
        if len(msgs) < page_size:
            break
        cur_anchor = msgs[-1]["id"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull Zulip DM submissions into weekN/submissions/")
    ap.add_argument("--week", type=int, required=True, help="Homework week number")
    ap.add_argument("--zuliprc", default=".zuliprc", help="Path to bot zuliprc")
    ap.add_argument("--roster", default="coursedesign/roster.csv", help="Path to roster CSV")
    ap.add_argument("--since", help="ISO 8601 lower bound, e.g. 2026-05-15T09:00")
    ap.add_argument("--until", help="ISO 8601 upper bound (inclusive)")
    args = ap.parse_args()

    zuliprc = Path(args.zuliprc)
    if not zuliprc.exists():
        print(f"error: {zuliprc} not found; run /setup-zulip-grading first", file=sys.stderr)
        return 1

    roster_path = Path(args.roster)
    roster = load_roster(roster_path)

    week_dir = Path(f"week{args.week}")
    submissions_dir = week_dir / "submissions"
    unknown_dir = submissions_dir / "_unknown"
    state_path = week_dir / "zulip-pull.json"

    state = load_state(state_path)
    anchor = int(state.get("last_message_id") or 0)
    after_ts = parse_iso(args.since) if args.since else None
    until_ts = parse_iso(args.until) if args.until else None

    bot_email, api_key, site = read_zuliprc_site(zuliprc)
    client = zulip.Client(config_file=str(zuliprc))

    try:
        messages = fetch_all_dms(client, anchor=anchor, after_ts=after_ts, until_ts=until_ts)
    except Exception as e:
        print(f"error: fetching DMs failed: {e}", file=sys.stderr)
        return 2

    per_student: dict[str, int] = {}
    unknowns: dict[str, dict[str, Any]] = {}
    files_written = 0
    fetched_ids: list[int] = list(state.get("fetched_message_ids", []))
    max_id = anchor

    for msg in messages:
        if msg["sender_email"].lower() == bot_email.lower():
            continue
        attachments = [(label, url) for label, url in extract_attachment_urls(msg.get("content", "")) if looks_like_attachment(label, url)]
        if not attachments:
            continue

        sender_email = msg["sender_email"].lower()
        sender_name = msg.get("sender_full_name", "")
        roster_row = roster.get(sender_email)

        for n, (label, url) in enumerate(attachments, start=1):
            original = slug_filename(label or url.rsplit("/", 1)[-1])
            if roster_row:
                sid = roster_row["student_id"]
                fname = f"{slug_filename(sid)}_{msg['id']}_{n}_{original}"
                dest = submissions_dir / fname
            else:
                fname = f"{msg['id']}_{n}_{original}"
                dest = unknown_dir / fname

            try:
                download_attachment(site, url, bot_email, api_key, dest)
            except Exception as e:
                print(f"warn: download failed for msg {msg['id']} attachment {n}: {e}", file=sys.stderr)
                continue
            files_written += 1

            if roster_row:
                per_student[roster_row["student_id"]] = per_student.get(roster_row["student_id"], 0) + 1
            else:
                unknowns.setdefault(sender_email, {
                    "sender_email": sender_email,
                    "sender_name": sender_name,
                    "files": 0,
                })
                unknowns[sender_email]["files"] += 1

        fetched_ids.append(msg["id"])
        max_id = max(max_id, msg["id"])

    new_state = {
        "last_pull_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "last_message_id": max_id,
        "fetched_message_ids": fetched_ids,
    }
    write_state(state_path, new_state)

    summary = {
        "week": args.week,
        "messages_seen": len(messages),
        "files_written": files_written,
        "students": per_student,
        "unknowns": list(unknowns.values()),
        "submissions_dir": str(submissions_dir),
        "state_path": str(state_path),
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
