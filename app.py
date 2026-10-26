import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def run_query(sql, params=None):
    with psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [column.name for column in cursor.description]
            rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=columns)


st.title("GO Transit Tracker")
st.write("Questions about the GO Transit schedule, answered with SQL on PostgreSQL.")


# 1. Milton line trains from Milton GO on a weekday morning (queries.sql, query 1)
st.header("Milton line trains from Milton GO, weekday mornings")

weekdays = run_query(
    """
    SELECT DISTINCT date
    FROM calendar_dates
    WHERE EXTRACT(ISODOW FROM date) BETWEEN 1 AND 5
    ORDER BY date
    """
)
chosen_date = st.selectbox("Weekday", weekdays["date"])

milton_trains = run_query(
    """
    SELECT
        TO_CHAR(stop_times.departure_time, 'HH24:MI') AS departure,
        trips.trip_headsign AS destination,
        trips.trip_id
    FROM stop_times
    JOIN trips ON trips.trip_id = stop_times.trip_id
    JOIN routes ON routes.route_id = trips.route_id
    JOIN calendar_dates ON calendar_dates.service_id = trips.service_id
    WHERE routes.route_short_name = 'MI'
      AND routes.route_type = 2
      AND stop_times.stop_id = 'ML'
      AND trips.direction_id = 1
      AND calendar_dates.date = %s
      AND stop_times.departure_time < INTERVAL '12 hours'
    ORDER BY stop_times.departure_time
    """,
    (chosen_date,),
)
st.write("Trains on this date:", len(milton_trains))
st.dataframe(milton_trains, hide_index=True)


# 2. Routes serving Sheridan College (queries.sql, query 2)
st.header("Routes serving Sheridan College")

sheridan_routes = run_query(
    """
    SELECT DISTINCT
        routes.route_short_name AS route,
        routes.route_long_name AS name
    FROM stop_times
    JOIN trips ON trips.trip_id = stop_times.trip_id
    JOIN routes ON routes.route_id = trips.route_id
    WHERE stop_times.stop_id = '00939'
    ORDER BY routes.route_short_name
    """
)
st.dataframe(sheridan_routes, hide_index=True)


# 3. Trips per route (queries.sql, query 3)
st.header("Trips per route")

trips_per_route = run_query(
    """
    SELECT
        routes.route_short_name AS route,
        routes.route_long_name AS name,
        COUNT(trips.trip_id) AS trips
    FROM routes
    JOIN trips ON trips.route_id = routes.route_id
    GROUP BY routes.route_short_name, routes.route_long_name
    ORDER BY trips DESC
    """
)
st.dataframe(trips_per_route, hide_index=True)
