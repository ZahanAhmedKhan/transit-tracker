import csv
import os
from datetime import datetime

import psycopg
from dotenv import load_dotenv

BATCH_SIZE = 50000


def read_gtfs_file(file_name):
    path = "data/" + file_name
    with open(path, encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    return rows


def empty_to_none(value):
    if value == "":
        return None
    return value


def load_trips(cursor):
    trips = read_gtfs_file("trips.txt")
    rows = []
    for trip in trips:
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

    cursor.execute("DELETE FROM trips")
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


def load_calendar_dates(cursor):
    calendar_dates = read_gtfs_file("calendar_dates.txt")
    rows = []
    for calendar_date in calendar_dates:
        rows.append(
            (
                calendar_date["service_id"],
                datetime.strptime(calendar_date["date"], "%Y%m%d").date(),
                int(calendar_date["exception_type"]),
            )
        )

    cursor.execute("DELETE FROM calendar_dates")
    cursor.executemany(
        "INSERT INTO calendar_dates (service_id, date, exception_type) VALUES (%s, %s, %s)",
        rows,
    )
    print("Calendar dates loaded:", len(rows))


def insert_stop_times(cursor, batch):
    cursor.executemany(
        """
        INSERT INTO stop_times (trip_id, stop_sequence, stop_id, arrival_time, departure_time,
                                pickup_type, drop_off_type, stop_headsign)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        batch,
    )


def load_stop_times(cursor):
    cursor.execute("DELETE FROM stop_times")
    batch = []
    total = 0

    with open("data/stop_times.txt", encoding="utf-8-sig") as file:
        for stop_time in csv.DictReader(file):
            batch.append(
                (
                    stop_time["trip_id"],
                    int(stop_time["stop_sequence"]),
                    stop_time["stop_id"],
                    stop_time["arrival_time"],
                    stop_time["departure_time"],
                    int(stop_time["pickup_type"]),
                    int(stop_time["drop_off_type"]),
                    empty_to_none(stop_time["stop_headsign"]),
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


load_dotenv()

with psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
) as connection:
    with connection.cursor() as cursor:
        load_trips(cursor)
        load_calendar_dates(cursor)
        load_stop_times(cursor)
