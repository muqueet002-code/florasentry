"""Create the first administrator account.

There is deliberately NO default admin password anywhere in this repository. A seeded
`admin/admin` is how demo systems become real breaches (TRD 37.3).

The password is read from the ADMIN_PASSWORD environment variable, or prompted for
interactively. It is never written to a file, a log or an audit payload.

Usage:
    python scripts/create_admin_user.py --email admin@example.org --name "Site Admin"
    ADMIN_PASSWORD=... python scripts/create_admin_user.py --email ... --name ...
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.rbac import UserRole  # noqa: E402
from app.core.security import hash_password, validate_password_strength  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402
from app.services.audit_service import AuditService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a FloraSentry admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--username", default=None)
    args = parser.parse_args()

    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            print(
                "ERROR: no ADMIN_PASSWORD in the environment and stdin is not a terminal.",
                file=sys.stderr,
            )
            return 2
        password = getpass.getpass("Admin password: ")
        if password != getpass.getpass("Confirm password: "):
            print("ERROR: passwords do not match.", file=sys.stderr)
            return 2

    try:
        validate_password_strength(password)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    with session_scope() as db:
        repo = UserRepository(db)
        if repo.email_exists(args.email):
            print(f"ERROR: a user with email {args.email} already exists.", file=sys.stderr)
            return 1

        user = repo.create(
            full_name=args.name,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            email=args.email,
            username=args.username,
        )
        AuditService(db).record(
            action="ADMIN_USER_CREATED",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            actor_role=UserRole.ADMIN.value,
            after_state={"email": args.email, "role": "ADMIN"},
        )
        print(f"Created ADMIN user {args.email} (id={user.id})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
