"""Run a .sql file against the database in .env (local PostgreSQL or Supabase).

Usage:  python run_sql.py schema.sql
"""

import sys

from db import get_connection


def run_sql_file(path):
    """Read a SQL file and run all of its statements in one transaction."""
    with open(path, encoding="utf-8") as file:
        sql = file.read()

    with get_connection() as connection:
        connection.execute(sql)

    print("Ran", path)


if __name__ == "__main__":
    run_sql_file(sys.argv[1])
