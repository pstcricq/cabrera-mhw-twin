"""Year explorer: one year and one warming scenario, on the map and day by day.

The year and the scenario live in the URL, so a link reopens the same view.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import (
    CATEGORY_COLOURS,
    COLOURS,
    HEAT_SCALE,
    MAP_CONFIG,
    base_map,
    events_table,
    fetch,
    fmt_date,
    footer,
    mpa_ring,
    style,
    table,
)

CATEGORY_ORDER = ["Moderate", "Strong", "Severe", "Extreme"]

meta = fetch("/meta")
last = pd.Timestamp(meta["last_date"])
observed = table("/indicators/yearly")
years = sorted(observed.year.tolist(), reverse=True)
scenarios = meta["scenarios"]

params = st.query_params
asked_year = params.get("year", "")
default_year = int(asked_year) if asked_year.isdigit() else years[0]
default_delta = params.get("delta", "0")

st.title("Year explorer")
st.markdown(
    "Where and when the MPA was in heatwave in a given year, and how the same year "
    "would look in a uniformly warmer sea."
)

pick_year, pick_delta = st.columns([1, 3], vertical_alignment="bottom")
year = pick_year.selectbox(
    "Year", years, index=years.index(default_year) if default_year in years else 0
)
delta = pick_delta.segmented_control(
    "What-if warming",
    scenarios,
    default=default_delta if default_delta in scenarios else "0",
    format_func=lambda d: "Observed" if d == "0" else f"+{d} °C",
    help=(
        "Adds a uniform warming to the observed series and keeps the 1991-2020 "
        "threshold: a sensitivity test, not a climate projection."
    ),
)
delta = delta or "0"
st.query_params.update({"year": str(year), "delta": delta})
warming = float(delta)
warm_label = f" at +{delta} °C" if warming else ""

obs_row = observed[observed.year == year].iloc[0]
row = table("/indicators/yearly", delta=warming).set_index("year").loc[year]
events = table("/events", order_by="start", limit=1000)
year_events = events[
    (events.start.dt.year <= year) & (events.end.dt.year >= year)
].sort_values("start")
partial = obs_row.n_days < 365

# The year in four figures
days, summer, share, count = st.columns(4)
days.metric(
    f"Heatwave days{warm_label}",
    int(row.mhw_days),
    delta=(
        f"{int(row.mhw_days - obs_row.mhw_days):+d} vs observed"
        if warming
        else f"of {int(obs_row.n_days)} days"
        + (f" (to {fmt_date(last)})" if partial else "")
    ),
    delta_color="inverse" if warming else "off",
    delta_arrow="auto" if warming else "off",
    border=True,
    height="stretch",
)
summer.metric(
    f"Summer heatwave days{warm_label}",
    int(row.summer_mhw_days),
    delta="June to October",
    delta_color="off",
    delta_arrow="off",
    border=True,
    height="stretch",
)
share.metric(
    f"Share of the MPA in heatwave{warm_label}",
    f"{row.area_percent:.0f} %",
    delta=(
        f"{row.area_percent - obs_row.area_percent:+.0f} points vs observed"
        if warming
        else "yearly mean, pixel by pixel"
    ),
    delta_color="inverse" if warming else "off",
    delta_arrow="auto" if warming else "off",
    border=True,
    height="stretch",
)
strongest = max(year_events.category, key=CATEGORY_ORDER.index, default=None)
count.metric(
    "Heatwave events (observed)",
    len(year_events),
    delta=f"strongest: {strongest}" if strongest else "none this year",
    delta_color=CATEGORY_COLOURS.get(strongest, "off"),
    delta_arrow="off",
    border=True,
    height="stretch",
)

where, when = st.columns([1, 1.15])

# Where: heatwave days per pixel
with where.container(border=True, height="stretch"):
    st.subheader("Heatwave days per pixel")
    fixed = st.toggle(
        "Same colour scale for every year",
        help="Off: colours span this year's range, to show where. "
        "On: 0 to 366 days, to compare years.",
    )
    cells = table("/grid", year=int(year), delta=warming)
    half = np.diff(np.sort(cells.latitude.unique())).min() / 2
    features = [
        {
            "type": "Feature",
            "id": str(i),
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [c.longitude - half, c.latitude - half],
                        [c.longitude + half, c.latitude - half],
                        [c.longitude + half, c.latitude + half],
                        [c.longitude - half, c.latitude + half],
                        [c.longitude - half, c.latitude - half],
                    ]
                ],
            },
        }
        for i, c in enumerate(cells.itertuples())
    ]
    lons, lats = mpa_ring()
    station = meta["station"]
    fig = go.Figure(
        [
            go.Choroplethmap(
                geojson={"type": "FeatureCollection", "features": features},
                locations=[f["id"] for f in features],
                z=cells.mhw_days,
                zmin=0 if fixed else cells.mhw_days.min(),
                zmax=366 if fixed else cells.mhw_days.max(),
                colorscale=HEAT_SCALE,
                marker_opacity=0.85,
                marker_line_width=0,
                colorbar={"title": "days", "thickness": 10, "len": 0.7, "x": 1},
                customdata=np.stack(
                    [
                        cells.latitude,
                        cells.longitude,
                        np.where(cells.in_mpa, "inside the MPA", "outside the MPA"),
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{z} heatwave days</b><br>%{customdata[0]:.3f}°N "
                    "%{customdata[1]:.3f}°E, %{customdata[2]}<extra></extra>"
                ),
                showlegend=False,
            ),
            go.Scattermap(
                lon=lons,
                lat=lats,
                mode="lines",
                line={"width": 2, "color": COLOURS["text"]},
                name="MPA boundary",
                hoverinfo="skip",
            ),
            go.Scattermap(
                lon=[station["lon"]],
                lat=[station["lat"]],
                mode="markers",
                marker={"size": 10, "color": COLOURS["sst"]},
                name="SOCIB station",
                hovertemplate=f"{station['name']}<extra></extra>",
            ),
        ]
    )
    st.plotly_chart(
        base_map(fig, cells.longitude, cells.latitude, zoom=8.3, height=400),
        config=MAP_CONFIG,
    )
    st.caption(
        "Detection run independently on each 0.05° satellite pixel, against that "
        "pixel's own climatology. Black outline: MPA. Blue dot: SOCIB station."
    )

# When: the daily series
with when.container(border=True, height="stretch"):
    st.subheader("Daily SST over the MPA")
    daily = table("/indicators/daily", year=int(year))
    wash_top = np.where(
        daily.mhw, np.maximum(daily.sst, daily.threshold), daily.threshold
    )
    hover = "%{y:.2f} °C"
    traces = [
        go.Scatter(
            x=daily.date,
            y=daily.climatology,
            name="Climatology",
            line={"color": COLOURS["climatology"], "width": 1.5},
            hovertemplate=hover,
        ),
        go.Scatter(
            x=daily.date,
            y=daily.threshold,
            name="Threshold (P90)",
            line={"color": COLOURS["threshold"], "width": 1.5, "dash": "dash"},
            hovertemplate=hover,
        ),
        go.Scatter(
            x=daily.date,
            y=wash_top,
            fill="tonexty",
            fillcolor=COLOURS["heatwave_wash"],
            line={"width": 0},
            name="Heatwave day",
            hoverinfo="skip",
        ),
        go.Scatter(
            x=daily.date,
            y=daily.sst,
            name="SST",
            line={"color": COLOURS["sst"], "width": 2},
            hovertemplate=hover,
        ),
    ]
    if warming:
        traces.append(
            go.Scatter(
                x=daily.date,
                y=daily.sst + warming,
                name=f"SST +{delta} °C",
                line={"color": COLOURS["sst"], "width": 1.5, "dash": "dot"},
                opacity=0.7,
                hovertemplate=hover,
            )
        )
    fig = go.Figure(traces)
    style(fig, 400)
    fig.update_layout(
        hovermode="x unified",
        margin={"l": 40, "r": 0, "t": 8, "b": 0},
        legend={"orientation": "h", "y": -0.12, "yanchor": "top", "x": 0},
    )
    fig.update_xaxes(tickformat="%b", hoverformat="%-d %b %Y")
    fig.update_yaxes(ticksuffix=" °C")
    st.plotly_chart(fig, config={"displayModeBar": False})
    st.caption(
        "Mean of the pixels inside the MPA. Orange: days inside a detected heatwave"
        + (f"; the dotted line is the same year {delta} °C warmer." if warming else ".")
    )

# The events
with st.container(border=True):
    st.subheader(f"Heatwave events in {year}")
    if year_events.empty:
        st.markdown(f"No marine heatwave was detected in {year}.")
    else:
        events_table(year_events)
        st.caption(
            "Observed events overlapping the year; an event can straddle two years. "
            "Intensities are departures from the climatology."
        )

footer(meta)
