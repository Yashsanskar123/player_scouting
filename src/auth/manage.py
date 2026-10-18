"""User administration from the command line (works even before anyone can sign in).

  python -m src.auth.manage create-user alice --role admin
  python -m src.auth.manage set-password alice
  python -m src.auth.manage list
Passwords are prompted (or read from SCOUTIQ_NEW_PASSWORD) and never echoed or logged.
"""
from __future__ import annotations

import argparse
import getpass
import os

from src.auth import service
from src.auth.permissions import ROLES
from src.auth.security import hash_password
from src.db.session import SessionLocal


def _password() -> str:
    return os.getenv("SCOUTIQ_NEW_PASSWORD") or getpass.getpass("Password: ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user"); c.add_argument("username"); c.add_argument("--role", choices=ROLES, default="analyst"); c.add_argument("--name")
    p = sub.add_parser("set-password"); p.add_argument("username")
    sub.add_parser("list")
    args = parser.parse_args(argv)
    service.ensure_auth_tables()
    with SessionLocal() as session:
        if args.cmd == "list":
            for u in session.query(service.User).order_by(service.User.username):
                print(f"{u.username:24} {u.role:9} {'active' if u.is_active else 'disabled'}")
        elif args.cmd == "create-user":
            service.create_user(session, args.username, _password(), args.role, args.name)
            print(f"Created {args.role} '{service.normalize_username(args.username)}'.")
        else:
            user = service.get_user(session, args.username)
            if not user:
                print("No such user."); return 1
            pw = _password(); service.validate_password(pw)
            user.password_hash = hash_password(pw); session.commit(); service.clear_failures(user.username)
            print("Password updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
