"""Load trips, calendar_dates and stop_times from the files in data/.

To fit Supabase's 500 MB free tier, only service dates inside a window are kept:
from DAYS_BEFORE days ago up to DAYS_AFTER days ahead (see docs/decisions.md).
"""

import csv
from datetime import date, datetime, timedelta

from db import get_connection

BATCH_SIZE = 50000
DAYS_BEFORE = 3
DAYS_AFTER = 14


def read_gtfs_file(file_name):
    """Read a whole GTFS file from data/ into a list of dictionaries."""
    path = "data/" + file_name
    with open(path, encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    return rows


def empty_to_none(value):
    """Turn an empty CSV value into None so it is stored as NULL."""
    if value == "":
        return None
    return value


def parse_gtfs_date(text):
    """Turn a GTFS date such as 20261125 into a Python date."""
    return datetime.strptime(text, "%Y%m%d").date()


def is_in_window(service_date, today):
    """Return True if a service date falls inside the window that is kept."""
    first_day = today - timedelta(days=DAYS_BEFORE)
    last_day = today + timedelta(days=DAYS_AFTER)
    return first_day <= service_date <= last_day


def load_calendar_dates(cursor, today):
    """Load the calendar dates inside the window and return their service_ids."""
    rows = []
    for calendar_date in read_gtfs_file("calendar_dates.txt"):
        service_date = parse_gtfs_date(calendar_date["date"])
        if is_in_window(service_date, today):
            rows.append(
                (calendar_date["service_id"], service_date, int(calendar_date["exception_type"]))
            )

    cursor.execute("DELETE FROM calendar_dates")
    cursor.executemany(
        "INSERT INTO calendar_dates (service_id, date, exception_type) VALUES (%s, %s, %s)",
        rows,
    )
    print("Calendar dates loaded:", len(rows))
    return {row[0] for row in rows}


def load_trips(cursor, service_ids):
    """Load the trips that run on the kept service_ids and return their trip_ids."""
    rows = []
    for trip in read_gtfs_file("trips.txt"):
        if trip["service_id"] in service_ids:
            rows.append(
                (
                    trip["trip_id"],
                    trip["route_id"],
                    trip["service_id"],
                    trip["trip_headsign"],
                    empty_to_none(trip["trip_short_name"]),
                    int(trip["direction_id"]),
                    trip["block_id"],
                    empty_to_none(trip["shape_id"]),
                    int(trip["wheelchair_accessible"]),
                    int(trip["bikes_allowed"]),
                    empty_to_none(trip["route_variant"]),
                )
            )

    cursor.execute("TRUNCATE trips")
    cursor.executemany(
        """
        INSERT INTO trips (trip_id, route_id, service_id, trip_headsign, trip_short_name,
                           direction_id, block_id, shape_id, wheelchair_accessible,
                           bikes_allowed, route_variant)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    print("Trips loaded:", len(rows))
    return {row[0] for row in rows}


def insert_stop_times(cursor, batch):
    """Insert one batch of stop_times rows."""
    cursor.executemany(
        """
        INSERT INTO stop_times (trip_id, stop_sequence, stop_id, arrival_time, departure_time,
                                pickup_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        batch,
    )


def load_stop_times(cursor, trip_ids):
    """Stream stop_times.txt and load the rows of the kept trips in batches."""
    # TRUNCATE empties the table and frees its space at once; DELETE would leave
    # dead rows behind every day the schedule is reloaded.
    cursor.execute("TRUNCATE stop_times")
    batch = []
    total = 0

    with open("data/stop_times.txt", encoding="utf-8-sig") as file:
        for stop_time in csv.DictReader(file):
            if stop_time["trip_id"] not in trip_ids:
                continue
            batch.append(
                (
                    stop_time["trip_id"],
                    int(stop_time["stop_sequence"]),
                    stop_time["stop_id"],
                    stop_time["arrival_time"],
                    stop_time["departure_time"],
                    int(stop_time["pickup_type"]),
                )
            )

            if len(batch) == BATCH_SIZE:
                insert_stop_times(cursor, batch)
                total = total + len(batch)
                print("Stop times loaded so far:", total)
                batch = []

    if len(batch) > 0:
        insert_stop_times(cursor, batch)
        total = total + len(batch)

    print("Stop times loaded:", total)


if __name__ == "__main__":
    today = date.today()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            kept_service_ids = load_calendar_dates(cursor, today)
            kept_trip_ids = load_trips(cursor, kept_service_ids)
            load_stop_times(cursor, kept_trip_ids)
