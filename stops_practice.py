import csv

with open("data/stops.txt", encoding="utf-8-sig") as file:
    rows = list(csv.DictReader(file))

print(len(rows))
print(type(rows))
print(type(rows[0]["stop_lat"]))

first = rows[0]
print(first.keys())
print(first["stop_name"])

for row in rows[:3]:
    print(row["stop_id"], row["stop_name"])

