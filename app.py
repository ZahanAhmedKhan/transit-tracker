from datetime import date, time, timedelta

import pydeck as pdk
import streamlit as st

import queries

# Street map with road and place names.
MAP_STYLE = pdk.map_styles.CARTO_ROAD

# Look of the box that appears when you hover over a stop on any map.
TOOLTIP_STYLE = {
    "backgroundColor": "white",
    "color": "#222",
    "fontFamily": "sans-serif",
    "fontSize": "13px",
    "padding": "6px 10px",
    "borderRadius": "6px",
    "boxShadow": "0 2px 8px rgba(0, 0, 0, 0.25)",
}


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
    # Only the start and end names are drawn; the stops in between show on hover,
    # so their names never overlap.
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
    view = pdk.data_utils.compute_view(path)
    st.pydeck_chart(
        pdk.Deck(
            layers=[line_layer, stop_layer, end_names_layer],
            initial_view_state=view,
            map_style=MAP_STYLE,
            tooltip={
                "html": "<b>{stop_name}</b><br/>Arrives {arrival} ({minutes} min)",
                "style": TOOLTIP_STYLE,
            },
        ),
        height=550,
    )
    st.dataframe(stops[["stop_name", "arrival", "minutes"]], hide_index=True)


# Routes need at least this many observed arrivals to be ranked best or worst.
MIN_ARRIVALS_TO_RANK = 50


def nice_date(day):
    """Format a date like 'November 25, 2026' (works on Windows and Linux)."""
    return f"{day:%B} {day.day}, {day.year}"


def delay_color(minutes):
    """Colour for a stop on the reliability map: green on time, through yellow and orange, to red."""
    if minutes <= 1:
        return [26, 150, 65]
    if minutes <= 3:
        return [230, 190, 0]
    if minutes <= 5:
        return [245, 130, 30]
    return [215, 25, 28]


@st.cache_data(ttl=600)
def load_reliability():
    """Load every reliability table at once; cached for 10 minutes to spare the database."""
    return {
        "overall": queries.get_reliability_overall(),
        "routes": queries.get_reliability_by_route(MIN_ARRIVALS_TO_RANK),
        "hours": queries.get_reliability_by_hour(),
        "stops": queries.get_reliability_by_stop(),
    }


def show_headline(overall):
    """Show how much data there is, then the overall on-time rate and delays."""
    st.caption(
        f"Data collected since {nice_date(overall['first_service_date'])} "
        f"(latest summarized day: {nice_date(overall['last_service_date'])}) · "
        f"{overall['trips_tracked']:,} trips tracked · "
        f"{overall['observed_arrivals']:,} observed arrivals"
    )
    rate, average, p90, cancelled = st.columns(4)
    rate.metric("On-time rate", f"{overall['on_time_rate']:.1%}")
    average.metric("Average delay", f"{overall['avg_delay_minutes']:.1f} min")
    p90.metric("90% arrive within", f"{overall['p90_delay_minutes']:.1f} min")
    cancelled.metric("Cancelled trips", f"{overall['cancelled_trips']:,}")
    st.caption(
        "On time = between 1 minute early and 5 minutes late. Delays use observed arrivals "
        "only; skipped stops and cancelled trips are counted separately."
    )


def show_best_and_worst_routes(routes):
    """Show the five most and least punctual routes side by side."""
    if routes.empty:
        st.info(f"No route has {MIN_ARRIVALS_TO_RANK} observed arrivals yet.")
        return
    columns = {
        "route": "Route",
        "route_name": "Name",
        "on_time_rate": st.column_config.NumberColumn("On time", format="percent"),
        "avg_delay_minutes": st.column_config.NumberColumn("Avg delay (min)", format="%.1f"),
        "observed_arrivals": "Arrivals",
    }
    best_column, worst_column = st.columns(2)
    best_column.subheader("Most punctual routes")
    best_column.dataframe(
        routes.head(5), column_config=columns, column_order=list(columns), hide_index=True
    )
    worst_column.subheader("Least punctual routes")
    worst_column.dataframe(
        routes.tail(5).iloc[::-1], column_config=columns, column_order=list(columns),
        hide_index=True,
    )


def show_delay_by_hour(hours):
    """Bar chart of the average delay for each hour of the day."""
    st.subheader("Average delay by hour of day")
    st.bar_chart(
        hours, x="hour_of_day", y="avg_delay_minutes", x_label="Hour (Toronto time)",
        y_label="Average delay (min)",
    )


def show_delay_map(stops):
    """Map of stops coloured by their average delay."""
    st.subheader("Average delay by stop")
    st.caption("Green: up to 1 min · yellow: up to 3 · orange: up to 5 · red: more than 5 min late")
    stops = stops.copy()
    stops["color"] = stops["avg_delay_minutes"].apply(delay_color)
    stops["delay_text"] = stops["avg_delay_minutes"].map("{:.1f}".format)
    stops["on_time_text"] = stops["on_time_rate"].map("{:.0%}".format)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=stops,
        get_position=["longitude", "latitude"],
        get_fill_color="color",
        get_line_color=[255, 255, 255],
        stroked=True,
        line_width_min_pixels=1,
        radius_min_pixels=5,
        radius_max_pixels=10,
        pickable=True,
        auto_highlight=True,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(latitude=43.65, longitude=-79.6, zoom=8),
            map_style=MAP_STYLE,
            tooltip={
                "html": "<b>{stop_name}</b><br/>Average delay {delay_text} min<br/>"
                        "On time {on_time_text} ({observed_arrivals} arrivals)",
                "style": TOOLTIP_STYLE,
            },
        ),
        height=550,
    )


def show_reliability():
    """The Reliability tab: how late GO trains and buses really run."""
    data = load_reliability()
    overall = data["overall"].iloc[0]
    if not overall["observed_arrivals"]:
        st.info(
            "No live arrivals have been summarized yet. Live data is collected every "
            "5 minutes and summarized once a day, so the first numbers appear the day "
            "after collection starts."
        )
        return
    show_headline(overall)
    show_best_and_worst_routes(data["routes"])
    show_delay_by_hour(data["hours"])
    show_delay_map(data["stops"])


st.set_page_config(page_title="GO Transit Reliability Tracker", layout="wide")
st.title("GO Transit Reliability Tracker")
st.write(
    "How late GO trains and buses really run: live GO Transit data collected every 5 minutes "
    "and compared with the schedule, in PostgreSQL."
)

reliability_tab, departures_tab, routes_tab, trips_tab, map_tab = st.tabs(
    ["Reliability", "Departures", "Routes at a stop", "Trips per route", "Map of stops"]
)


# Tab 0: reliability from live data (Phase 2)
with reliability_tab:
    show_reliability()


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
    st.write(
        f"Trips each route runs in the loaded schedule "
        f"({nice_date(first_date)} to {nice_date(last_date)})."
    )
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
    st.write(f"{len(stops)} stops. Hover over a dot to see the stop's name.")
    # No always-on labels: GO has a stop on each side of many roads, so the names
    # would be drawn on top of each other. The name shows on hover instead.
    dot_layer = pdk.Layer(
        "ScatterplotLayer",
        data=stops,
        get_position=["longitude", "latitude"],
        get_fill_color=[0, 120, 70],
        get_line_color=[255, 255, 255],
        stroked=True,
        line_width_min_pixels=1,
        radius_min_pixels=4,
        radius_max_pixels=8,
        pickable=True,
        auto_highlight=True,
    )
    view = pdk.ViewState(latitude=43.65, longitude=-79.6, zoom=8)
    st.pydeck_chart(
        pdk.Deck(
            layers=[dot_layer],
            initial_view_state=view,
            map_style=MAP_STYLE,
            tooltip={"html": "<b>{stop_name}</b>", "style": TOOLTIP_STYLE},
        ),
        height=650,
    )
