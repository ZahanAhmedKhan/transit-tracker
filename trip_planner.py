"""Find GO Transit journeys from one stop to another, direct or with one change.

The search runs in SQL (see JOURNEYS_SQL); the functions below pick the useful
options and turn times into text. A journey with a change lets you walk up to
MAX_WALK_METRES between stops, because GO's train and bus stops at the same
station have different names (for example "Milton GO" and "Milton GO Bus").
"""

import pandas as pd

# How far you may walk to change between stops, and how fast.
MAX_WALK_METRES = 400
WALK_METRES_PER_MINUTE = 80
# Extra time to make any connection, on top of the walk.
CHANGE_BUFFER_MINUTES = 3
# Only journeys that leave within this many hours of the chosen time are searched.
SEARCH_HOURS = 3
# The most journeys shown at once.
MAX_OPTIONS = 6

# Every journey from the origin to the destination on one service date.
# Leg 1 is always filled; leg 2 is NULL for a direct trip.
# A degree of latitude is 111,320 m; a degree of longitude around Toronto is
# 111,320 m x cos(43.7°) = 80,500 m, which is close enough for walks of a few hundred metres.
JOURNEYS_SQL = """
WITH running AS (
    -- Trips that run on the chosen date.
    SELECT trips.trip_id
    FROM trips
    JOIN calendar_dates ON calendar_dates.service_id = trips.service_id
    WHERE calendar_dates.date = %(travel_date)s
      AND calendar_dates.exception_type = 1
),
boardings AS (
    -- Where and when you can get on at the origin.
    SELECT stop_times.trip_id, stop_times.stop_sequence, stop_times.departure_time
    FROM stop_times
    JOIN running ON running.trip_id = stop_times.trip_id
    JOIN stops ON stops.stop_id = stop_times.stop_id
    WHERE stops.stop_name = %(from_name)s
      AND stop_times.pickup_type = 0
      AND stop_times.departure_time >= CAST(%(leave_after)s AS INTERVAL)
      AND stop_times.departure_time < CAST(%(leave_after)s AS INTERVAL) + %(search_hours)s * INTERVAL '1 hour'
),
arrivals AS (
    -- Where and when you can get off at the destination.
    SELECT stop_times.trip_id, stop_times.stop_sequence, stop_times.arrival_time
    FROM stop_times
    JOIN running ON running.trip_id = stop_times.trip_id
    JOIN stops ON stops.stop_id = stop_times.stop_id
    WHERE stops.stop_name = %(to_name)s
      AND stop_times.arrival_time >= CAST(%(leave_after)s AS INTERVAL)
),
direct AS (
    SELECT boardings.trip_id AS trip_1, boardings.stop_sequence AS board_1,
           boardings.departure_time AS depart_1,
           arrivals.stop_sequence AS alight_1, arrivals.arrival_time AS arrive_1,
           NULL::TEXT AS trip_2, NULL::INTEGER AS board_2, NULL::INTERVAL AS depart_2,
           NULL::INTEGER AS alight_2, NULL::INTERVAL AS arrive_2, NULL::INTEGER AS walk_metres
    FROM boardings
    JOIN arrivals
      ON arrivals.trip_id = boardings.trip_id
     AND arrivals.stop_sequence > boardings.stop_sequence
),
first_legs AS (
    -- Every stop you can ride to from the origin: a possible place to change.
    SELECT boardings.trip_id, boardings.stop_sequence AS board_sequence, boardings.departure_time,
           later.stop_id AS change_stop, later.stop_sequence AS change_sequence,
           later.arrival_time AS change_arrival
    FROM boardings
    JOIN stop_times AS later
      ON later.trip_id = boardings.trip_id
     AND later.stop_sequence > boardings.stop_sequence
),
second_legs AS (
    -- Every stop where you can get on a trip that later reaches the destination.
    SELECT arrivals.trip_id, earlier.stop_id AS board_stop, earlier.stop_sequence AS board_sequence,
           earlier.departure_time, arrivals.stop_sequence AS alight_sequence, arrivals.arrival_time
    FROM arrivals
    JOIN stop_times AS earlier
      ON earlier.trip_id = arrivals.trip_id
     AND earlier.stop_sequence < arrivals.stop_sequence
    WHERE earlier.pickup_type = 0
      AND earlier.departure_time >= CAST(%(leave_after)s AS INTERVAL)
),
walks AS (
    -- Pairs of stops close enough to walk between (a stop to itself is 0 m).
    SELECT here.stop_id AS from_stop, there.stop_id AS to_stop,
           ROUND(SQRT(POWER((here.stop_lat - there.stop_lat) * 111320, 2)
                    + POWER((here.stop_lon - there.stop_lon) * 80500, 2)))::INTEGER AS metres
    FROM stops AS here
    JOIN stops AS there
      ON ABS(here.stop_lat - there.stop_lat) < 0.005
     AND ABS(here.stop_lon - there.stop_lon) < 0.007
),
one_change AS (
    SELECT first_legs.trip_id, first_legs.board_sequence, first_legs.departure_time,
           first_legs.change_sequence, first_legs.change_arrival,
           second_legs.trip_id, second_legs.board_sequence, second_legs.departure_time,
           second_legs.alight_sequence, second_legs.arrival_time, walks.metres
    FROM first_legs
    JOIN walks ON walks.from_stop = first_legs.change_stop
    JOIN second_legs ON second_legs.board_stop = walks.to_stop
    WHERE walks.metres <= %(max_walk)s
      AND second_legs.trip_id <> first_legs.trip_id
      AND second_legs.departure_time >= first_legs.change_arrival
          + (CEIL(walks.metres::NUMERIC / %(walk_speed)s) + %(buffer)s) * INTERVAL '1 minute'
),
journeys AS (
    SELECT * FROM direct
    UNION ALL
    SELECT * FROM one_change
)
-- Add the route of each leg (route_type 2 is a train, 3 a bus).
SELECT journeys.*,
       route_1.route_short_name AS route_1, route_1.route_type AS type_1,
       route_2.route_short_name AS route_2, route_2.route_type AS type_2
FROM journeys
JOIN trips AS trip_1 ON trip_1.trip_id = journeys.trip_1
JOIN routes AS route_1 ON route_1.route_id = trip_1.route_id
LEFT JOIN trips AS trip_2 ON trip_2.trip_id = journeys.trip_2
LEFT JOIN routes AS route_2 ON route_2.route_id = trip_2.route_id
"""


def best_journeys(journeys):
    """Keep only the useful journeys, earliest arrival first.

    A journey is dropped when another one leaves at the same time or later and
    arrives at the same time or earlier (with no more changes when they tie).
    """
    if journeys.empty:
        return journeys
    journeys = journeys.copy()
    journeys["changes"] = journeys["trip_2"].notna().astype(int)
    journeys["arrive"] = journeys["arrive_2"].fillna(journeys["arrive_1"])
    # Latest departure first; among those, earliest arrival, then fewest changes.
    journeys = journeys.sort_values(
        ["depart_1", "arrive", "changes"], ascending=[False, True, True]
    )
    kept = []
    earliest_arrival_so_far = None
    for _, journey in journeys.iterrows():
        if earliest_arrival_so_far is None or journey["arrive"] < earliest_arrival_so_far:
            kept.append(journey)
            earliest_arrival_so_far = journey["arrive"]
    best = pd.DataFrame(kept).sort_values("arrive")
    return best.head(MAX_OPTIONS).reset_index(drop=True)


def vehicle_name(route_type):
    """'Train' for GTFS route_type 2, otherwise 'Bus' (GO runs only trains and buses)."""
    return "Train" if route_type == 2 else "Bus"


def journey_summary(journey):
    """One line for the options table, like 'Bus 56 → Train LW'."""
    summary = f"{vehicle_name(journey['type_1'])} {journey['route_1']}"
    if journey["changes"]:
        summary += f" → {vehicle_name(journey['type_2'])} {journey['route_2']}"
    return summary


def clock_time(interval):
    """Turn a GTFS time like 25:10:00 (a timedelta) into a clock time like '01:10'."""
    total_minutes = int(interval.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours % 24:02d}:{minutes:02d}"


def duration_text(interval):
    """Turn a length of time into text like '1 h 05 min' or '42 min'."""
    total_minutes = int(interval.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    return f"{minutes} min"


def walk_minutes(metres):
    """Minutes to walk a distance at WALK_METRES_PER_MINUTE, at least 1."""
    return max(1, -(-int(metres) // WALK_METRES_PER_MINUTE))


def search_params(from_name, to_name, travel_date, leave_after):
    """The values JOURNEYS_SQL needs, with leave_after as 'HH:MM'."""
    return {
        "from_name": from_name,
        "to_name": to_name,
        "travel_date": travel_date,
        "leave_after": leave_after,
        "search_hours": SEARCH_HOURS,
        "max_walk": MAX_WALK_METRES,
        "walk_speed": WALK_METRES_PER_MINUTE,
        "buffer": CHANGE_BUFFER_MINUTES,
    }




def nearest_point(shape, latitude, longitude, start=0):
    """Position (0, 1, 2, ...) of the shape point closest to a stop, looking from `start` on."""
    rest = shape.iloc[start:]
    squared_distance = (rest["latitude"] - latitude) ** 2 + (rest["longitude"] - longitude) ** 2
    return start + int(squared_distance.to_numpy().argmin())


def cut_shape(shape, first_stop, last_stop):
    """The part of a trip's road path between where you get on and where you get off.

    shape has latitude and longitude columns in driving order; first_stop and
    last_stop are rows with latitude and longitude. Searching for the last stop
    only after the first one keeps loops (which pass a point twice) in order.
    """
    start = nearest_point(shape, first_stop["latitude"], first_stop["longitude"])
    end = nearest_point(shape, last_stop["latitude"], last_stop["longitude"], start)
    return shape.iloc[start:end + 1]
