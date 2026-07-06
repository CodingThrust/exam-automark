#!/usr/bin/env python3
"""DM per-student feedback markdown files back via the grading bot.

Reads ``weekN/grades/feedback/<student_id>.md`` for each student, looks up
their Zulip email via ``coursedesign/roster.csv``, and sends the markdown
as a private message.

Idempotent via ``weekN/zulip-feedback-sent.json``: already-sent students are
skipped unless ``--resend`` is passed. Messages longer than the Zulip 10K
character limit are split on blank-line boundaries.

Use ``--dry-run`` to preview without sending.

The caller (Claude in the loop) handles human review BEFORE invoking this
script. The script is the executor, not the reviewer.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import zulip


ZULIP_MESSAGE_LIMIT = 10_000


def load_roster(path: Path) -> dict[str, str]:
    """Return student_id -> zulip_email."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = (row.get("student_id") or "").strip()
            email = (row.get("zulip_email") or "").strip()
            if sid and email:
                out[sid] = email
    return out


def load_sent_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sent": [], "last_sent_at": None}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_sent_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def split_message(body: str, limit: int = ZULIP_MESSAGE_LIMIT) -> list[str]:
    if len(body) <= limit:
        return [body]
    parts: list[str] = []
    paragraphs = body.split("\n\n")
    cur = ""
    for p in paragraphs:
        candidate = (cur + "\n\n" + p).strip() if cur else p
        if len(candidate) > limit and cur:
            parts.append(cur)
            cur = p
        else:
            cur = candidate
    if cur:
        parts.append(cur)
    # If a single paragraph still exceeds, hard-split on character boundary.
    final: list[str] = []
    for p in parts:
        if len(p) <= limit:
            final.append(p)
        else:
            for i in range(0, len(p), limit):
                final.append(p[i : i + limit])
    return final


def make_header(week: int) -> str:
    return f"**Homework {week} feedback** — reply here with questions.\n\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="DM per-student feedback files")
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--zuliprc", default=".zuliprc")
    ap.add_argument("--roster", default="coursedesign/roster.csv")
    ap.add_argument("--student-ids", help="Comma-separated student_ids to send; default: all in feedback dir")
    ap.add_argument("--resend", action="store_true", help="Send even to students already in the sent state")
    ap.add_argument("--dry-run", action="store_true", help="Print what would be sent without sending")
    args = ap.parse_args()

    week_dir = Path(f"week{args.week}")
    feedback_dir = week_dir / "grades" / "feedback"
    sent_state_path = week_dir / "zulip-feedback-sent.json"

    if not feedback_dir.is_dir():
        print(f"error: {feedback_dir} not found; run /grade-homework first", file=sys.stderr)
        return 1

    roster_path = Path(args.roster)
    sid_to_email = load_roster(roster_path)
    sent_state = load_sent_state(sent_state_path)
    already_sent = set(sent_state.get("sent", []))

    feedback_files = sorted(feedback_dir.glob("*.md"))
    if not feedback_files:
        print(f"warn: no feedback files in {feedback_dir}", file=sys.stderr)

    if args.student_ids:
        wanted = {s.strip() for s in args.student_ids.split(",") if s.strip()}
        feedback_files = [p for p in feedback_files if p.stem in wanted]

    if not args.dry_run:
        zuliprc = Path(args.zuliprc)
        if not zuliprc.exists():
            print(f"error: {zuliprc} not found; run /setup-zulip-grading first", file=sys.stderr)
            return 1
        client = zulip.Client(config_file=str(zuliprc))
    else:
        client = None

    sent: list[str] = []
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    header = make_header(args.week)

    for fb in feedback_files:
        sid = fb.stem
        if sid in already_sent and not args.resend:
            skipped.append({"student_id": sid, "reason": "already_sent"})
            continue
        email = sid_to_email.get(sid)
        if not email:
            skipped.append({"student_id": sid, "reason": "no_roster_email"})
            continue

        body = header + fb.read_text(encoding="utf-8")
        chunks = split_message(body)

        if args.dry_run:
            print(f"dry-run: would send {len(chunks)} message(s) to {email} ({sid})", file=sys.stderr)
            sent.append(sid)
            continue

        ok = True
        for chunk in chunks:
            result = client.send_message({
                "type": "private",
                "to": [email],
                "content": chunk,
            })
            if result.get("result") != "success":
                failed.append({"student_id": sid, "email": email, "reason": result.get("msg", "unknown")})
                ok = False
                break
        if ok:
            sent.append(sid)

    if not args.dry_run and sent:
        already_sent.update(sent)
        sent_state["sent"] = sorted(already_sent)
        sent_state["last_sent_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        write_sent_state(sent_state_path, sent_state)

    summary = {
        "week": args.week,
        "dry_run": args.dry_run,
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
        "state_path": str(sent_state_path),
    }
    print(json.dumps(summary))
    return 0 if not failed else 4


if __name__ == "__main__":
    sys.exit(main())
