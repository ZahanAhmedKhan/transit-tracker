import csv

from db import get_connection

# shapes.txt holds the road path of every route as a list of points.
# Each shape_id is one path; shape_pt_sequence is the order of its points.

with get_connection() as connection:
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS shapes")
        cursor.execute(
            """
            CREATE TABLE shapes (
                shape_id           TEXT,
                shape_pt_sequence  INTEGER,
                shape_pt_lat       DOUBLE PRECISION,
                shape_pt_lon       DOUBLE PRECISION,
                PRIMARY KEY (shape_id, shape_pt_sequence)
            )
            """
        )

        # COPY streams all rows to PostgreSQL in one go, much faster than INSERT.
        total = 0
        with open("data/shapes.txt", encoding="utf-8-sig") as file:
            with cursor.copy(
                "COPY shapes (shape_id, shape_pt_sequence, shape_pt_lat, shape_pt_lon) FROM STDIN"
            ) as copy:
                for point in csv.DictReader(file):
                    copy.write_row(
                        (
                            point["shape_id"],
                            int(point["shape_pt_sequence"]),
                            float(point["shape_pt_lat"]),
                            float(point["shape_pt_lon"]),
                        )
                    )
                    total = total + 1

        print("Shape points loaded:", total)
        cursor.execute("SELECT COUNT(DISTINCT shape_id) FROM shapes")
        print("Shapes:", cursor.fetchone()[0])
