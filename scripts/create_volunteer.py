"""CLI to create (or promote) a volunteer account.

Run from the project root:

    python -m scripts.create_volunteer --email vol@example.com --password "secret123" --name "Gate Vol"

Volunteers cannot be created through the public API by design — this script is the
only way to mint one, which keeps the privileged role off the open registration path.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Role, User
from app.security import hash_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or promote a volunteer account.")
    parser.add_argument("--email", required=True, help="Volunteer email")
    parser.add_argument("--password", required=True, help="Volunteer password (min 8 chars)")
    parser.add_argument("--name", default="Volunteer", help="Display name")
    args = parser.parse_args(argv)

    init_db()
    email = args.email.strip().lower()

    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role == Role.volunteer:
                print(f"User {email} is already a volunteer.")
                return 0
            existing.role = Role.volunteer
            db.commit()
            print(f"Promoted existing user {email} to volunteer.")
            return 0

        if len(args.password) < 8:
            print("Password must be at least 8 characters.", file=sys.stderr)
            return 2

        user = User(
            name=args.name.strip(),
            email=email,
            password_hash=hash_password(args.password),
            role=Role.volunteer,
        )
        db.add(user)
        db.commit()
        print(f"Created volunteer {email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
