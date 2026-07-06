#!/usr/bin/env python3
"""Create a Zulip generic bot via the API and write its zuliprc.

Reads the instructor's API key from the ZULIP_API_KEY env var (never argv).

Outputs the new bot's identity as a single JSON line on stdout. Writes the
bot's zuliprc to the path given by --out.

Exit codes:
  0 success
  2 realm forbids bot creation by this user
  3 a bot with that short_name already exists
  4 other API error (auth, network, malformed input)
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import sys
from pathlib import Path

import zulip


SHORT_NAME_RE = re.compile(r"[^a-z0-9-]+")


def slug(s: str) -> str:
    return SHORT_NAME_RE.sub("-", s.lower()).strip("-")


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a Zulip grading bot")
    ap.add_argument("--site", required=True, help="Zulip realm URL, e.g. https://yourorg.zulipchat.com")
    ap.add_argument("--instructor-email", required=True, help="Instructor's Zulip login email")
    ap.add_argument("--course-code", required=True, help="Course code, e.g. DSAA3071")
    ap.add_argument("--out", default=".zuliprc", help="Path to write the bot's zuliprc (default: .zuliprc)")
    ap.add_argument("--full-name", help="Override default full name '<course-code> grading bot'")
    ap.add_argument("--short-name", help="Override default short name '<course-code>-grading'")
    args = ap.parse_args()

    api_key = os.environ.get("ZULIP_API_KEY")
    if not api_key:
        print("error: ZULIP_API_KEY env var is empty or missing", file=sys.stderr)
        return 4

    site = args.site.rstrip("/")
    if not site.startswith(("http://", "https://")):
        site = "https://" + site

    full_name = args.full_name or f"{args.course_code} grading bot"
    short_name = args.short_name or slug(f"{args.course_code}-grading")

    try:
        client = zulip.Client(email=args.instructor_email, api_key=api_key, site=site)
    except Exception as e:
        print(f"error: could not construct Zulip client: {e}", file=sys.stderr)
        return 4

    try:
        result = client.call_endpoint(
            "users/me/bots",
            method="POST",
            request={"full_name": full_name, "short_name": short_name, "bot_type": 1},
        )
    except Exception as e:
        print(f"error: API call failed: {e}", file=sys.stderr)
        return 4

    if result.get("result") != "success":
        msg = result.get("msg", "unknown error")
        code = result.get("code", "")
        print(f"error: Zulip API returned failure: {msg} ({code})", file=sys.stderr)
        if "bot_creation" in msg.lower() or "permission" in msg.lower() or code == "BAD_REQUEST" and "policy" in msg.lower():
            return 2
        if "already exists" in msg.lower() or code == "BAD_REQUEST" and "short_name" in msg.lower():
            return 3
        return 4

    bot_email = result["email"]
    bot_api_key = result["api_key"]
    bot_user_id = result["user_id"]

    out_path = Path(args.out)
    cfg = configparser.ConfigParser()
    cfg["api"] = {"email": bot_email, "key": bot_api_key, "site": site}
    with out_path.open("w", encoding="utf-8") as f:
        cfg.write(f)
    out_path.chmod(0o600)

    print(json.dumps({
        "email": bot_email,
        "user_id": bot_user_id,
        "full_name": full_name,
        "short_name": short_name,
        "zuliprc_path": str(out_path),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
