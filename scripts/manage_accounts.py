#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import sys
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import main  # noqa: E402


def add_account(account: str, display_name: str | None) -> int:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    try:
        created = main.provision_managed_account(account, password, display_name)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        print(f"Account was not created: {detail}", file=sys.stderr)
        return 1
    print(json.dumps(created, ensure_ascii=False))
    return 0


def list_accounts() -> int:
    with main._MEETING_DB_LOCK, closing(main._meeting_db()) as connection:
        rows = connection.execute(
            "SELECT id, account, display_name, created_at FROM accounts ORDER BY created_at"
        ).fetchall()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
    return 0


def cli() -> int:
    parser = argparse.ArgumentParser(description="Manage invited VoiceNote accounts on the server")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parser = subparsers.add_parser("add", help="create one invited account; password is prompted securely")
    add_parser.add_argument("account", help="username or email")
    add_parser.add_argument("--display-name", help="optional display name")
    subparsers.add_parser("list", help="list account metadata without password material")
    args = parser.parse_args()
    if args.command == "add":
        return add_account(args.account, args.display_name)
    return list_accounts()


if __name__ == "__main__":
    raise SystemExit(cli())
