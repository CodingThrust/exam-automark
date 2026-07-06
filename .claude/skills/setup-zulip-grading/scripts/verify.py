#!/usr/bin/env python3
"""Verify that a zuliprc still authenticates against its realm.

Prints the bot/user profile as a single JSON line on success.

Exit codes:
  0 success
  1 config file missing or unreadable
  2 auth failed (revoked, wrong site, network)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import zulip


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify a zuliprc against the Zulip API")
    ap.add_argument("--config", default=".zuliprc", help="Path to the zuliprc (default: .zuliprc)")
    args = ap.parse_args()

    path = Path(args.config)
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 1

    try:
        client = zulip.Client(config_file=str(path))
    except Exception as e:
        print(f"error: could not load {path}: {e}", file=sys.stderr)
        return 1

    try:
        profile = client.get_profile()
    except Exception as e:
        print(f"error: get_profile failed: {e}", file=sys.stderr)
        return 2

    if profile.get("result") != "success":
        print(f"error: profile call returned: {profile.get('msg', 'unknown')}", file=sys.stderr)
        return 2

    out = {
        "email": profile.get("email"),
        "full_name": profile.get("full_name"),
        "user_id": profile.get("user_id"),
        "is_bot": profile.get("is_bot", False),
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
