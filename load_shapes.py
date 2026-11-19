"""Load route paths from data/shapes.txt.

shapes.txt holds the road path of every route as a list of points. Each shape_id
is one path; shape_pt_sequence is the order of its points. Only the shapes used by
the trips already in the database are kept, so run load_trips_times.py first.
"""

import csv

from db import get_connection

CREATE_SHAPES_SQL = """
CREATE TABLE shapes (
    shape_id           TEXT,
    shape_pt_sequence  INTEGER,
    shape_pt_lat       DOUBLE PRECISION,
    shape_pt_lon       DOUBLE PRECISION,
    PRIMARY KEY (shape_id, shape_pt_sequence)
)
"""


def get_used_shape_ids(cursor):
    """Return the set of shape_ids that the loaded trips use."""
    cursor.execute("SELECT DISTINCT shape_id FROM trips WHERE shape_id IS NOT NULL")
    return {row[0] for row in cursor.fetchall()}


def copy_shapes(cursor, shape_ids):
    """Stream the points of the used shapes with COPY and return how many were loaded."""
    total = 0
    with open("data/shapes.txt", encoding="utf-8-sig") as file:
        # COPY streams all rows to PostgreSQL in one go, much faster than INSERT.
        with cursor.copy(
            "COPY shapes (shape_id, shape_pt_sequence, shape_pt_lat, shape_pt_lon) FROM STDIN"
        ) as copy:
            for point in csv.DictReader(file):
                if point["shape_id"] not in shape_ids:
                    continue
                copy.write_row(
                    (
                        point["shape_id"],
                        int(point["shape_pt_sequence"]),
                        float(point["shape_pt_lat"]),
                        float(point["shape_pt_lon"]),
                    )
                )
                total = total + 1
    return total


if __name__ == "__main__":
    with get_connection() as connection:
        with connection.cursor() as cursor:
            used_shape_ids = get_used_shape_ids(cursor)
            cursor.execute("DROP TABLE IF EXISTS shapes")
            cursor.execute(CREATE_SHAPES_SQL)
            print("Shape points loaded:", copy_shapes(cursor, used_shape_ids))
            print("Shapes:", len(used_shape_ids))
