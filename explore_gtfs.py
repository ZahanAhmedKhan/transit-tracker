import csv


def read_gtfs_file(file_name):
    path = "data/" + file_name
    with open(path, encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    return rows


def find_stops(stops, search_text):
    matches = []
    for stop in stops:
        if search_text.lower() in stop["stop_name"].lower().split():
            matches.append(stop)
    return matches


def count_by_type(routes):
    counts = {}
    for route in routes:
        route_type = route["route_type"]
        if route_type not in counts:
            counts[route_type] = 0
        counts[route_type] = counts[route_type] + 1
    return counts



stops = read_gtfs_file("stops.txt")
routes = read_gtfs_file("routes.txt")

print("Number of stops:", len(stops))
print("Number of routes:", len(routes))
print("Stop columns:", list(stops[0].keys()))
print("Route columns:", list(routes[0].keys()))

print()
print("Stops with 'milton' in the name:")
milton_stops = find_stops(stops, "milton")
for stop in milton_stops:
    print(stop["stop_id"], "|", stop["stop_name"])
print("Matches:", len(milton_stops))

print()
print("Stops with 'sheridan' in the name:")
for stop in find_stops(stops, "sheridan"):
    print(stop["stop_id"], "|", stop["stop_name"])

print()
print("All routes:")
for route in routes:
    print(route["route_short_name"], "|", route["route_long_name"], "| type", route["route_type"])

print()
print("Routes per route_type (2 = rail, 3 = bus):")
print(count_by_type(routes))
