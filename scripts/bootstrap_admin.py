"""Bootstrap the first platform admin account.

The normal platform-user APIs require an existing platform admin, so fresh
deployments need one direct database bootstrap step.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import Settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import migrate_database, open_database_connection  # noqa: E402
from app.services._sql import execute, fetch_one  # noqa: E402


DEFAULT_PASSWORD_ENV = "EXPERT_BOOTSTRAP_ADMIN_PASSWORD"


def main() -> int:
    args = _parse_args()
    email = args.email.strip().lower()
    settings = _settings_from_args(args)

    if not args.no_migrate and settings.database_auto_migrate:
        migrate_database(settings)

    with open_database_connection(settings) as connection:
        user = fetch_one(connection, "select id, status from users where email = ? limit 1", (email,))
        password = args.password or os.environ.get(args.password_env)

        if user:
            user_id = str(user["id"])
            if args.reset_password:
                password = password or _prompt_password()
                execute(
                    connection,
                    """
                    update users
                    set password_hash = ?, name = ?, status = 'active', updated_at = ?
                    where id = ?
                    """,
                    (hash_password(password), args.name, _now_iso(), user_id),
                )
                password_message = "password reset"
            else:
                password_message = "password unchanged"
        else:
            password = password or _prompt_password()
            user_id = args.user_id or f"user_{uuid4().hex}"
            execute(
                connection,
                """
                insert into users (id, email, password_hash, name, status)
                values (?, ?, ?, ?, 'active')
                """,
                (user_id, email, hash_password(password), args.name),
            )
            password_message = "password set"

        role = fetch_one(
            connection,
            """
            select id from platform_user_roles
            where user_id = ? and role = 'admin'
            limit 1
            """,
            (user_id,),
        )
        if not role:
            execute(
                connection,
                """
                insert into platform_user_roles (id, user_id, role, assigned_by)
                values (?, ?, 'admin', null)
                """,
                (f"platform_role_{uuid4().hex}", user_id),
            )

        connection.commit()

    print(f"Bootstrapped platform admin: {email} ({user_id}), {password_message}.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or promote a platform admin user.")
    parser.add_argument(
        "--email",
        default=os.environ.get("EXPERT_BOOTSTRAP_ADMIN_EMAIL", "admin@example.com"),
        help="Admin email. Defaults to EXPERT_BOOTSTRAP_ADMIN_EMAIL or admin@example.com.",
    )
    parser.add_argument(
        "--name",
        default=os.environ.get("EXPERT_BOOTSTRAP_ADMIN_NAME", "Platform Admin"),
        help="Admin display name. Defaults to EXPERT_BOOTSTRAP_ADMIN_NAME or Platform Admin.",
    )
    parser.add_argument(
        "--password",
        help=f"Admin password. If omitted, reads {DEFAULT_PASSWORD_ENV} or prompts when needed.",
    )
    parser.add_argument(
        "--password-env",
        default=DEFAULT_PASSWORD_ENV,
        help=f"Environment variable to read the password from. Defaults to {DEFAULT_PASSWORD_ENV}.",
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("EXPERT_BOOTSTRAP_ADMIN_USER_ID"),
        help="User id for a newly created admin. Defaults to a generated user_<uuid> id.",
    )
    parser.add_argument(
        "--database-url",
        help="Override EXPERT_DATABASE_URL for this run.",
    )
    parser.add_argument(
        "--no-migrate",
        action="store_true",
        help="Skip schema migration before bootstrapping.",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset the password when the email already exists.",
    )
    return parser.parse_args()


def _settings_from_args(args: argparse.Namespace) -> Settings:
    overrides = {"database_url": args.database_url}
    return Settings(**{key: value for key, value in overrides.items() if value is not None})


def _prompt_password() -> str:
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if not password:
        raise SystemExit("Password cannot be empty.")
    return password


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
