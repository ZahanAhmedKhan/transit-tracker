"""Fetch GO Transit's live feeds once and store them. GitHub Actions runs this every 5 minutes.

Each feed gets one row in ingestion_runs. If any feed fails, the script exits with
code 1 so the GitHub Actions run shows a red X.

Usage:  python ingest.py
"""

import os
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from db import get_connection
from realtime_parse import parse_feed, trip_update_rows, vehicle_position_rows

BASE_URL = "https://api.openmetrolinx.com/OpenDataAPI/api/V1/Gtfs/Feed/"

TRIP_UPDATE_COLUMNS = [
    "snapshot_time", "trip_id", "service_date", "route_id", "stop_id", "stop_sequence",
    "arrival_time", "departure_time", "arrival_delay", "departure_delay",
    "stop_relationship", "trip_relationship",
]
TRIP_UPDATE_KEY = [
    "trip_id", "service_date", "stop_id", "stop_sequence", "arrival_time", "departure_time",
    "arrival_delay", "departure_delay", "stop_relationship", "trip_relationship",
]
VEHICLE_COLUMNS = [
    "snapshot_time", "vehicle_id", "position_time", "trip_id", "route_id",
    "latitude", "longitude", "bearing", "speed",
]


def fetch_feed_bytes(feed_path, api_key):
    """Download one feed from the Metrolinx Open Data API and return the raw bytes."""
    request = Request(
        BASE_URL + feed_path + "?key=" + api_key,
        headers={"Accept": "application/x-protobuf"},
    )
    with urlopen(request, timeout=60) as response:
        return response.read()


def copy_to_staging(cursor, table_name, rows, columns):
    """Make an empty temporary copy of a table's columns and COPY the rows into it.

    The temporary table disappears at the end of the transaction.
    """
    cursor.execute("DROP TABLE IF EXISTS staging")
    cursor.execute(
        f"CREATE TEMP TABLE staging ON COMMIT DROP AS "
        f"SELECT {', '.join(columns)} FROM {table_name} WITH NO DATA"
    )
    with cursor.copy(f"COPY staging ({', '.join(columns)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row([row[column] for column in columns])


def store_trip_updates(cursor, rows):
    """Insert new trip-update rows, refresh last_seen_at on repeats, and return how many were new.

    Re-running the same snapshot inserts nothing (the unique key matches), so ingestion is
    idempotent. RETURNING (xmax = 0) is true only for rows that were newly inserted.
    """
    copy_to_staging(cursor, "rt_trip_updates", rows, TRIP_UPDATE_COLUMNS)
    columns = ", ".join(TRIP_UPDATE_COLUMNS)
    cursor.execute(
        f"""
        INSERT INTO rt_trip_updates ({columns}, last_seen_at)
        SELECT DISTINCT ON ({', '.join(TRIP_UPDATE_KEY)}) {columns}, snapshot_time
        FROM staging
        ON CONFLICT ON CONSTRAINT rt_trip_updates_unique
        DO UPDATE SET last_seen_at = GREATEST(rt_trip_updates.last_seen_at, EXCLUDED.last_seen_at)
        RETURNING (xmax = 0) AS inserted
        """
    )
    return sum(1 for (inserted,) in cursor.fetchall() if inserted)


def store_vehicle_positions(cursor, rows):
    """Insert vehicle positions, skipping ones already stored, and return how many were new."""
    copy_to_staging(cursor, "rt_vehicle_positions", rows, VEHICLE_COLUMNS)
    columns = ", ".join(VEHICLE_COLUMNS)
    cursor.execute(
        f"""
        INSERT INTO rt_vehicle_positions ({columns})
        SELECT DISTINCT ON (vehicle_id, position_time) {columns}
        FROM staging
        ON CONFLICT ON CONSTRAINT rt_vehicle_positions_unique DO NOTHING
        RETURNING position_id
        """
    )
    return len(cursor.fetchall())


# feed name -> (API path, function that turns the feed into rows, function that stores them)
FEEDS = {
    "TripUpdates": ("TripUpdates", trip_update_rows, store_trip_updates),
    "VehiclePositions": ("VehiclePosition", vehicle_position_rows, store_vehicle_positions),
}


def log_run(connection, feed_name, started_at, status, fetched, inserted, error_message):
    """Write one row to ingestion_runs describing how a feed's run went."""
    connection.execute(
        """
        INSERT INTO ingestion_runs (feed_name, started_at, finished_at, status,
                                    rows_fetched, rows_inserted, error_message)
        VALUES (%s, %s, now(), %s, %s, %s, %s)
        """,
        (feed_name, started_at, status, fetched, inserted, error_message),
    )
    connection.commit()


def safe_error(error, api_key):
    """Return a short error message with the API key removed, so it can be logged."""
    message = f"{type(error).__name__}: {error}"[:500]
    return message.replace(api_key, "<key>") if api_key else message


def ingest_feed(connection, feed_name, api_key):
    """Fetch, parse and store one feed, log the run, and return True if it worked."""
    feed_path, make_rows, store_rows = FEEDS[feed_name]
    started_at = datetime.now(timezone.utc)
    fetched = None
    try:
        feed = parse_feed(fetch_feed_bytes(feed_path, api_key))
        rows = make_rows(feed, started_at)
        fetched = len(rows)
        with connection.cursor() as cursor:
            inserted = store_rows(cursor, rows) if rows else 0
        connection.commit()
    except Exception as error:
        connection.rollback()
        message = safe_error(error, api_key)
        log_run(connection, feed_name, started_at, "failed", fetched, None, message)
        print(f"{feed_name}: FAILED - {message}")
        return False

    log_run(connection, feed_name, started_at, "success", fetched, inserted, None)
    print(f"{feed_name}: fetched {fetched} rows, inserted {inserted} new rows")
    return True


def main():
    """Ingest every feed once and exit with code 1 if any of them failed."""
    api_key = os.getenv("METROLINX_API_KEY")
    if not api_key:
        sys.exit("METROLINX_API_KEY is not set (see docs/setup.md).")

    start = time.perf_counter()
    with get_connection() as connection:
        results = [ingest_feed(connection, name, api_key) for name in FEEDS]
    print(f"Finished in {time.perf_counter() - start:.1f} s")

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
