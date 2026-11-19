import pandas as pd

from db import get_connection


def run_query(sql, params=None):
    # Runs one SQL query and returns the result as a pandas DataFrame.
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [column.name for column in cursor.description]
            rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=columns)


# A stop matches when one of its words starts with the search text, so
# "Milton GO" finds "Milton GO" and "Milton GO Bus" but not "Hamilton GO Centre".
NAME_MATCH = "(stops.stop_name ILIKE %(name)s || '%%' OR stops.stop_name ILIKE '%% ' || %(name)s || '%%')"


def get_service_dates():
    # First and last date in the schedule, for the date picker.
    return run_query("SELECT MIN(date) AS first_date, MAX(date) AS last_date FROM calendar_dates")


def get_departures(station_name, travel_date, start_time, end_time):
    # Departures from stops matching station_name on travel_date between two times ("HH:MM").
    sql = f"""
        SELECT
            TO_CHAR(stop_times.departure_time, 'HH24:MI') AS departure,
            routes.route_short_name AS route,
            trips.trip_headsign AS destination,
            stops.stop_name AS stop,
            trips.trip_id,
            stop_times.stop_sequence
        FROM stop_times
        JOIN stops ON stops.stop_id = stop_times.stop_id
        JOIN trips ON trips.trip_id = stop_times.trip_id
        JOIN routes ON routes.route_id = trips.route_id
        JOIN calendar_dates ON calendar_dates.service_id = trips.service_id
        WHERE {NAME_MATCH}
          AND calendar_dates.date = %(date)s
          AND calendar_dates.exception_type = 1
          AND stop_times.departure_time BETWEEN CAST(%(start)s AS INTERVAL) AND CAST(%(end)s AS INTERVAL)
          AND stop_times.pickup_type = 0
          -- A departure needs a later stop; this leaves out trips that end here.
          AND EXISTS (
              SELECT 1
              FROM stop_times AS later
              WHERE later.trip_id = stop_times.trip_id
                AND later.stop_sequence > stop_times.stop_sequence
          )
        ORDER BY stop_times.departure_time, routes.route_short_name
    """
    params = {"name": station_name, "date": travel_date, "start": start_time, "end": end_time}
    return run_query(sql, params)


def get_routes_at_stop(stop_name):
    # Every route with at least one trip stopping at a stop matching stop_name.
    sql = f"""
        SELECT DISTINCT
            routes.route_short_name AS route,
            routes.route_long_name AS route_name,
            stops.stop_name AS stop
        FROM stop_times
        JOIN stops ON stops.stop_id = stop_times.stop_id
        JOIN trips ON trips.trip_id = stop_times.trip_id
        JOIN routes ON routes.route_id = trips.route_id
        WHERE {NAME_MATCH}
        ORDER BY routes.route_short_name, stops.stop_name
    """
    return run_query(sql, {"name": stop_name})


def get_trips_per_route():
    # Number of trips each route runs over the whole schedule, busiest first.
    sql = """
        SELECT
            routes.route_short_name AS route,
            routes.route_long_name AS route_name,
            COUNT(trips.trip_id) AS trips
        FROM routes
        JOIN trips ON trips.route_id = routes.route_id
        GROUP BY routes.route_short_name, routes.route_long_name
        ORDER BY trips DESC
    """
    return run_query(sql)


def get_trip_info(trip_id):
    # Route name, official colour and destination of one trip.
    sql = """
        SELECT
            routes.route_short_name AS route,
            routes.route_long_name AS route_name,
            routes.route_type,
            routes.route_color,
            trips.trip_headsign AS destination,
            trips.shape_id
        FROM trips
        JOIN routes ON routes.route_id = trips.route_id
        WHERE trips.trip_id = %(trip_id)s
    """
    return run_query(sql, {"trip_id": trip_id})


def get_trip_stops(trip_id, from_sequence):
    # The stops a trip makes from from_sequence to the end, with minutes since leaving.
    sql = """
        SELECT
            stops.stop_name,
            stops.stop_lat AS latitude,
            stops.stop_lon AS longitude,
            TO_CHAR(stop_times.arrival_time, 'HH24:MI') AS arrival,
            EXTRACT(EPOCH FROM stop_times.arrival_time - first_stop.departure_time) / 60 AS minutes
        FROM stop_times
        JOIN stops ON stops.stop_id = stop_times.stop_id
        JOIN stop_times AS first_stop
          ON first_stop.trip_id = stop_times.trip_id
         AND first_stop.stop_sequence = %(from_sequence)s
        WHERE stop_times.trip_id = %(trip_id)s
          AND stop_times.stop_sequence >= %(from_sequence)s
        ORDER BY stop_times.stop_sequence
    """
    stops = run_query(sql, {"trip_id": trip_id, "from_sequence": from_sequence})
    stops["minutes"] = stops["minutes"].astype(int)
    return stops


def get_trip_shape(shape_id):
    # The road path of a trip as points in driving order.
    sql = """
        SELECT shape_pt_lat AS latitude, shape_pt_lon AS longitude
        FROM shapes
        WHERE shape_id = %(shape_id)s
        ORDER BY shape_pt_sequence
    """
    return run_query(sql, {"shape_id": shape_id})


def get_all_stops():
    # Every stop with its position, for the map.
    sql = """
        SELECT stop_id, stop_name, stop_lat AS latitude, stop_lon AS longitude
        FROM stops
        ORDER BY stop_name
    """
    return run_query(sql)


# Reliability (Phase 2). These read the views in metrics_schema.sql; see docs/metrics.md.

RATE_AND_DELAY_COLUMNS = ["on_time_rate", "avg_delay_minutes", "p90_delay_minutes"]


def run_reliability_query(sql, params=None):
    """Run a reliability query and turn its rate and delay columns into plain floats.

    PostgreSQL NUMERIC values arrive as Python Decimals, which charts cannot plot.
    """
    result = run_query(sql, params)
    for column in RATE_AND_DELAY_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").astype(float)
    return result


def get_reliability_overall():
    """One row: date range, trips tracked, on-time rate and delays over all live data."""
    return run_reliability_query("SELECT * FROM reliability_overall")


def get_reliability_by_route(min_arrivals):
    """On-time rate and delays per route, for routes with at least min_arrivals observations."""
    sql = """
        SELECT route_short_name AS route, route_name, trips_tracked, observed_arrivals,
               on_time_rate, avg_delay_minutes, p90_delay_minutes, skipped_stops, cancelled_trips
        FROM reliability_by_route
        WHERE observed_arrivals >= %(min_arrivals)s
        ORDER BY on_time_rate DESC, avg_delay_minutes
    """
    return run_reliability_query(sql, {"min_arrivals": min_arrivals})


def get_reliability_by_hour():
    """Average and 90th-percentile delay for each hour of the day (Toronto time)."""
    sql = """
        SELECT hour_of_day, observed_arrivals, on_time_rate, avg_delay_minutes, p90_delay_minutes
        FROM reliability_by_hour
        WHERE observed_arrivals > 0
        ORDER BY hour_of_day
    """
    return run_reliability_query(sql)


def get_reliability_by_stop():
    """Average delay and on-time rate per stop, with coordinates for the map."""
    sql = """
        SELECT stop_id, stop_name, stop_lat AS latitude, stop_lon AS longitude,
               observed_arrivals, on_time_rate, avg_delay_minutes, p90_delay_minutes
        FROM reliability_by_stop
        WHERE observed_arrivals > 0 AND stop_lat IS NOT NULL
    """
    return run_reliability_query(sql)
