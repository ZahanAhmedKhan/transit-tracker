"""Print the database size and the size of every table, to watch Supabase's 500 MB limit.

Usage:  python measure_size.py
"""

from db import get_connection

TABLE_SIZES_SQL = """
SELECT
    relname AS table_name,
    n_live_tup AS approximate_rows,
    pg_size_pretty(pg_table_size(relid)) AS data_size,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(relid) DESC
"""


def print_database_size(cursor):
    """Print the total size of the whole database."""
    cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    print("Database size:", cursor.fetchone()[0])


def print_table_sizes(cursor):
    """Print rows, data size, index size and total size for each table."""
    cursor.execute(TABLE_SIZES_SQL)
    print(f"{'table':<24}{'rows':>12}{'data':>12}{'indexes':>12}{'total':>12}")
    for name, rows, data_size, index_size, total_size in cursor.fetchall():
        print(f"{name:<24}{rows:>12,}{data_size:>12}{index_size:>12}{total_size:>12}")


if __name__ == "__main__":
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE")
            print_database_size(cursor)
            print_table_sizes(cursor)
