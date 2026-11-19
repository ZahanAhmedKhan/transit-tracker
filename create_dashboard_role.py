"""Create a read-only database login for the public dashboard.

The deployed Streamlit app only needs to read, so it should not hold the admin password.
This script creates (or resets) the role dashboard_reader, which can only SELECT, gives it
a new random password, and writes its connection string to .env as DASHBOARD_DATABASE_URL.
Nothing secret is printed. Run it with the admin DATABASE_URL in .env:

    python create_dashboard_role.py
"""

import os
import secrets
from urllib.parse import urlsplit, urlunsplit

from psycopg import sql

from db import get_connection

ROLE_NAME = "dashboard_reader"

GRANT_STATEMENTS = [
    "GRANT USAGE ON SCHEMA public TO dashboard_reader",
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_reader",
    # Tables created later by the admin (load_shapes.py recreates shapes daily) are readable too.
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO dashboard_reader",
    "ALTER ROLE dashboard_reader SET default_transaction_read_only = on",
    "ALTER ROLE dashboard_reader SET statement_timeout = '30s'",
]


def create_or_reset_role(cursor, password):
    """Create the read-only role, or give it a new password if it already exists."""
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE_NAME,))
    action = "ALTER" if cursor.fetchone() else "CREATE"
    cursor.execute(
        sql.SQL(action + " ROLE {} WITH LOGIN PASSWORD {}").format(
            sql.Identifier(ROLE_NAME), sql.Literal(password)
        )
    )
    for statement in GRANT_STATEMENTS:
        cursor.execute(statement)


def reader_url(admin_url, password):
    """Build the reader's connection string from the admin one (same host, new user and password).

    Supabase's pooler expects user names of the form <role>.<project_ref>.
    """
    parts = urlsplit(admin_url)
    project_ref = parts.username.split(".", 1)[1] if "." in parts.username else ""
    user = f"{ROLE_NAME}.{project_ref}" if project_ref else ROLE_NAME
    netloc = f"{user}:{password}@{parts.hostname}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def save_to_env(name, value, env_path=".env"):
    """Set NAME=value in the .env file, replacing an existing line with that name."""
    with open(env_path, encoding="utf-8") as file:
        lines = [line for line in file.read().splitlines() if not line.startswith(name + "=")]
    lines.append(f"{name}={value}")
    with open(env_path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    new_password = secrets.token_urlsafe(24).replace("-", "a").replace("_", "b")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            create_or_reset_role(cursor, new_password)
    save_to_env("DASHBOARD_DATABASE_URL", reader_url(os.environ["DATABASE_URL"], new_password))
    print(f"Role {ROLE_NAME} is ready; DASHBOARD_DATABASE_URL was written to .env.")
