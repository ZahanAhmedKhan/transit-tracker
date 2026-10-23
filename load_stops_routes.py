import csv
import os

import psycopg
from dotenv import load_dotenv


def read_gtfs_file(file_name):
    path = "data/" + file_name
    with open(path, encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    return rows


def empty_to_none(value):
    if value == "":
        return None
    return value


def load_stops(cursor, stops):
    cursor.execute("DELETE FROM stops")
    for stop in stops:
        cursor.execute(
            """
            INSERT INTO stops (stop_id, stop_name, stop_lat, stop_lon, zone_id, stop_url,
                               location_type, parent_station, wheelchair_boarding, stop_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                stop["stop_id"],
                stop["stop_name"],
                float(stop["stop_lat"]),
                float(stop["stop_lon"]),
                stop["zone_id"],
                stop["stop_url"],
                int(stop["location_type"]),
                empty_to_none(stop["parent_station"]),
                int(stop["wheelchair_boarding"]),
                empty_to_none(stop["stop_code"]),
            ),
        )


def load_routes(cursor, routes):
    cursor.execute("DELETE FROM routes")
    for route in routes:
        cursor.execute(
            """
            INSERT INTO routes (route_id, agency_id, route_short_name, route_long_name,
                                route_type, route_color, route_text_color)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                route["route_id"],
                route["agency_id"],
                route["route_short_name"],
                route["route_long_name"],
                int(route["route_type"]),
                route["route_color"],
                route["route_text_color"],
            ),
        )


load_dotenv()

stops = read_gtfs_file("stops.txt")
routes = read_gtfs_file("routes.txt")

with psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
) as connection:
    with connection.cursor() as cursor:
        load_stops(cursor, stops)
        load_routes(cursor, routes)

        cursor.execute("SELECT COUNT(*) FROM stops")
        print("Stops in database:", cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM routes")
        print("Routes in database:", cursor.fetchone()[0])
