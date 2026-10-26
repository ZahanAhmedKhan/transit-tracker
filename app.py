from datetime import date, time, timedelta

import pydeck as pdk
import streamlit as st

import queries

# Street map with road and place names.
MAP_STYLE = pdk.map_styles.CARTO_ROAD


def hex_to_rgb(hex_color):
    # Turns GO's colour code like "f78025" into [247, 128, 37] for the map.
    return [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]


def show_trip(trip_id, stop_sequence, departure_time):
    # Draws one trip on a map in its route colour, with its stops and travel time.
    info = queries.get_trip_info(trip_id).iloc[0]
    stops = queries.get_trip_stops(trip_id, stop_sequence)
    color = hex_to_rgb(info["route_color"])
    vehicle = "Train" if info["route_type"] == 2 else "Bus"

    # Use the real road path when GO publishes one; otherwise join the stops.
    if info["shape_id"]:
        shape = queries.get_trip_shape(info["shape_id"])
    else:
        shape = stops[["latitude", "longitude"]]
    path = shape[["longitude", "latitude"]].values.tolist()

    # GO destinations start with the route, like "22 - Oakville GO"; keep the place only.
    destination = info["destination"].split(" - ", 1)[-1]

    first_stop = stops.iloc[0]
    last_stop = stops.iloc[-1]
    st.subheader(f"{vehicle} {info['route']} to {destination}")
    st.metric("Trip time", f"{last_stop['minutes']} min")
    st.write(
        f"Leaves {first_stop['stop_name']} at {departure_time}, "
        f"arrives at {last_stop['stop_name']} at {last_stop['arrival']} "
        f"({len(stops)} stops)."
    )

    line_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": path}],
        get_path="path",
        get_color=color,
        width_min_pixels=5,
    )
    stop_layer = pdk.Layer(
        "ScatterplotLayer",
        data=stops,
        get_position=["longitude", "latitude"],
        get_fill_color=[255, 255, 255],
        get_line_color=color,
        stroked=True,
        line_width_min_pixels=3,
        radius_min_pixels=6,
        pickable=True,
    )
    # Start and end names always show; the stops in between show as you zoom in.
    end_names_layer = pdk.Layer(
        "TextLayer",
        data=stops.iloc[[0, -1]],
        get_position=["longitude", "latitude"],
        get_text="stop_name",
        get_size=14,
        get_color=[30, 30, 30],
        get_pixel_offset=[0, -20],
        background=True,
        get_background_color=[255, 255, 255, 230],
        background_padding=[4, 2],
    )
    middle_names_layer = pdk.Layer(
        "TextLayer",
        data=stops.iloc[1:-1],
        get_position=["longitude", "latitude"],
        get_text="stop_name",
        get_size=150,
        size_units=pdk.types.String("meters"),
        size_max_pixels=13,
        get_color=[60, 60, 60],
        get_pixel_offset=[0, -14],
    )
    view = pdk.data_utils.compute_view(path)
    st.pydeck_chart(
        pdk.Deck(
            layers=[line_layer, stop_layer, middle_names_layer, end_names_layer],
            initial_view_state=view,
            map_style=MAP_STYLE,
            tooltip={"text": "{stop_name}\nArrives {arrival} ({minutes} min)"},
        ),
        height=550,
    )
    st.dataframe(stops[["stop_name", "arrival", "minutes"]], hide_index=True)


st.set_page_config(page_title="GO Transit Tracker", layout="wide")
st.title("GO Transit Tracker")
st.write("Questions about the GO Transit schedule, answered with SQL on PostgreSQL.")

departures_tab, routes_tab, trips_tab, map_tab = st.tabs(
    ["Departures", "Routes at a stop", "Trips per route", "Map of stops"]
)


# Tab 1: departures from a station on a date between two times
with departures_tab:
    service_dates = queries.get_service_dates()
    first_date = service_dates["first_date"][0]
    last_date = service_dates["last_date"][0]

    # Default to the next weekday in the schedule, from today.
    default_date = max(date.today(), first_date)
    while default_date.weekday() >= 5 and default_date < last_date:
        default_date = default_date + timedelta(days=1)
    default_date = min(default_date, last_date)

    station = st.text_input("Station or stop name", value="Milton GO")
    date_column, start_column, end_column = st.columns(3)
    travel_date = date_column.date_input(
        "Date", value=default_date, min_value=first_date, max_value=last_date
    )
    start_time = start_column.time_input("From", value=time(6, 0))
    end_time = end_column.time_input("To", value=time(10, 0))

    departures = queries.get_departures(
        station, travel_date, start_time.strftime("%H:%M"), end_time.strftime("%H:%M")
    )
    st.write(f"{len(departures)} departures. Click a row to see that trip on a map.")
    table = st.dataframe(
        departures,
        hide_index=True,
        column_order=["departure", "route", "destination", "stop"],
        on_select="rerun",
        selection_mode="single-row",
        key="departures_table",
    )

    # The map only appears after a row is clicked.
    selected_rows = table.selection.rows
    if selected_rows and selected_rows[0] < len(departures):
        row = departures.iloc[selected_rows[0]]
        show_trip(row["trip_id"], int(row["stop_sequence"]), row["departure"])


# Tab 2: routes that serve a stop
with routes_tab:
    stop_name = st.text_input("Stop name", value="Sheridan")
    routes = queries.get_routes_at_stop(stop_name)
    st.write(f"{len(routes)} routes")
    st.dataframe(routes, hide_index=True)


# Tab 3: number of trips per route
with trips_tab:
    trips_per_route = queries.get_trips_per_route()
    trips_per_route["route_label"] = trips_per_route["route"] + " " + trips_per_route["route_name"]
    st.write("Trips each route runs over the whole schedule (Sept 29 to Nov 27, 2026).")
    st.bar_chart(
        trips_per_route,
        x="route_label",
        y="trips",
        x_label="Route",
        y_label="Trips",
        horizontal=True,
        sort="-trips",
        height=900,
    )
    st.dataframe(trips_per_route[["route", "route_name", "trips"]], hide_index=True)


# Tab 4: every stop on a map
with map_tab:
    stops = queries.get_all_stops()
    st.write(f"{len(stops)} stops. Zoom in to read stop names; hover a dot for its name.")
    dot_layer = pdk.Layer(
        "ScatterplotLayer",
        data=stops,
        get_position=["longitude", "latitude"],
        get_fill_color=[0, 120, 70],
        radius_min_pixels=4,
        pickable=True,
    )
    # Names are sized in metres, so they are too small to see zoomed out and
    # become readable as you zoom in. pdk.types.String keeps "meters" as a plain
    # value; without it pydeck reads it as a column name and ignores the setting.
    name_layer = pdk.Layer(
        "TextLayer",
        data=stops,
        get_position=["longitude", "latitude"],
        get_text="stop_name",
        get_size=150,
        size_units=pdk.types.String("meters"),
        size_max_pixels=14,
        get_color=[30, 30, 30],
        get_pixel_offset=[0, -14],
    )
    view = pdk.ViewState(latitude=43.65, longitude=-79.6, zoom=8)
    st.pydeck_chart(
        pdk.Deck(
            layers=[dot_layer, name_layer],
            initial_view_state=view,
            map_style=MAP_STYLE,
            tooltip={"text": "{stop_name}"},
        ),
        height=650,
    )
