"""Overview: where the MPA stands today and how heatwaves have changed since 1982."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import (
    CATEGORY_COLOURS,
    COLOURS,
    MAP_CONFIG,
    base_map,
    fetch,
    fmt_date,
    footer,
    heat_chart,
    mpa_ring,
    style,
    table,
)

# Heatwave days are compared over the first and the last complete decade
DECADE = 10
SPARK_DAYS = 60

meta = fetch("/meta")
mpa = meta["mpa"]
last = pd.Timestamp(meta["last_date"])
yearly = table("/indicators/yearly")
spark_start = last - pd.Timedelta(days=SPARK_DAYS - 1)
recent_days = table("/indicators/daily", start=spark_start.date().isoformat())
today = recent_days.iloc[-1]

complete = yearly[yearly.n_days >= 365]
early = complete.head(DECADE)
early_mean = early.mhw_days.mean()
early_label = f"{early.year.min()}-{early.year.max()}"
recent = complete.tail(DECADE)
recent_mean = recent.mhw_days.mean()
recent_label = f"{recent.year.min()}-{recent.year.max()}"
record = yearly.loc[yearly.mhw_days.idxmax()]

st.caption("Digital Twin Ocean building block · Balearic Islands")
st.title("Marine heatwaves in the Cabrera National Park")
st.markdown(
    f"Daily satellite sea surface temperature since 1982 over the "
    f"{mpa['area_km2']} km² marine protected area, heatwaves detected with the "
    f"Hobday et al. method, and a check against the SOCIB station moored inside "
    f"the park."
)

# Today
MINI_CONFIG = {"displayModeBar": False}
now, sea = st.columns([3, 2])
with now.container(border=True, height="stretch"):
    current = meta["current_event"]
    if current:
        event_days = table("/indicators/daily", start=current["start"])
        st.metric(
            "Ongoing marine heatwave",
            f"{current['duration']} days",
            delta=current["category"],
            delta_color=CATEGORY_COLOURS[current["category"]],
            delta_arrow="off",
            delta_description=(
                f"since {fmt_date(current['start'])} · peak "
                f"+{current['intensity_max']:.2f} °C above climatology"
            ),
        )
        st.plotly_chart(
            heat_chart(
                event_days.date,
                event_days.sst - event_days.climatology,
                event_days.threshold - event_days.climatology,
                0 * event_days.sst,
                "Above climatology",
                "+.1f",
            ),
            config=MINI_CONFIG,
        )
        st.caption("Daily departure from climatology since the event began.")
    else:
        latest = table("/events", order_by="start", limit=1).iloc[0]
        st.metric(
            "No marine heatwave today",
            f"{(last - latest.end).days} days",
            delta=f"since the last one ended ({latest.category})",
            delta_color="off",
            delta_arrow="off",
        )
with sea.container(border=True, height="stretch"):
    anomaly = today.sst - today.climatology
    st.metric(
        f"Sea surface, {fmt_date(last)}",
        f"{today.sst:.1f} °C",
        delta=f"{anomaly:+.1f} °C vs normal",
        delta_color="inverse",
        delta_description=f"threshold {today.threshold:.1f} °C",
    )
    st.plotly_chart(
        heat_chart(
            recent_days.date,
            recent_days.sst,
            recent_days.threshold,
            recent_days.climatology,
            "SST",
            ".1f",
        ),
        config=MINI_CONFIG,
    )
    st.caption(f"MPA-mean SST over the last {SPARK_DAYS} days.")

# Then and now
first, second, third = st.columns(3)
first.metric(
    f"Heatwave days per year, {early_label}",
    f"{early_mean:.1f}",
    delta="first decade of the record",
    delta_color="off",
    delta_arrow="off",
    border=True,
    height="stretch",
)
second.metric(
    f"Heatwave days per year, {recent_label}",
    f"{recent_mean:.1f}",
    delta=f"×{recent_mean / early_mean:.0f} vs {early_label}",
    delta_color="inverse",
    delta_arrow="off",
    border=True,
    height="stretch",
)
third.metric(
    "Record year",
    int(record.year),
    delta=f"{int(record.mhw_days)} heatwave days",
    delta_color="off",
    delta_arrow="off",
    border=True,
    height="stretch",
)

# Trend and place
trend, place = st.columns([2, 1])
with trend.container(border=True, height="stretch"):
    st.subheader("Heatwave days per year")
    incomplete = yearly.n_days < 365
    colours = np.where(
        yearly.year == record.year,
        COLOURS["heatwave_dark"],
        COLOURS["heatwave_light"],
    )
    note = np.where(incomplete, f" (to {fmt_date(last)})", "")
    fig = go.Figure(
        go.Bar(
            x=yearly.year,
            y=yearly.mhw_days,
            marker_color=colours,
            marker_pattern_shape=np.where(incomplete, "/", ""),
            customdata=np.stack(
                [yearly.area_percent, yearly.intensity_cumulative, note], axis=-1
            ),
            hovertemplate=(
                "<b>%{x}</b>%{customdata[2]}<br>%{y} heatwave days<br>"
                "%{customdata[0]:.0f} % of the MPA on average<br>"
                "%{customdata[1]:.0f} °C·days cumulative intensity<extra></extra>"
            ),
        )
    )
    fig.add_hline(
        y=early_mean,
        line_dash="dot",
        line_color=COLOURS["muted"],
        annotation_text=f"{early_label} mean",
        annotation_position="top left",
        annotation_font_color=COLOURS["muted"],
    )
    fig.add_annotation(
        x=record.year,
        y=record.mhw_days,
        text=f"<b>{int(record.mhw_days)}</b>",
        showarrow=False,
        yshift=10,
    )
    fig.update_yaxes(title="days")
    event = st.plotly_chart(
        style(fig, 300),
        on_select="rerun",
        selection_mode="points",
        key="trend",
        config={"displayModeBar": False},
    )
    if event.selection.points:
        year = event.selection.points[0]["x"]
        st.switch_page("year_explorer.py", query_params={"year": str(year)})
    st.caption(
        "MPA-mean series. The hatched bar is the current, incomplete year. "
        "Click a year to open it in the Year explorer."
    )

with place.container(border=True, height="stretch"):
    st.subheader("Where")
    pixels = table("/grid", year=int(last.year), in_mpa=True)
    half = (np.diff(np.sort(pixels.latitude.unique())).min()) / 2
    box_lon, box_lat = [], []
    for p in pixels.itertuples():
        west, east = p.longitude - half, p.longitude + half
        south, north = p.latitude - half, p.latitude + half
        box_lon += [west, east, east, west, west, None]
        box_lat += [south, south, north, north, south, None]
    station = meta["station"]
    lons, lats = mpa_ring()
    fig = go.Figure(
        [
            go.Scattermap(
                lon=box_lon,
                lat=box_lat,
                mode="lines",
                line={"width": 0.7, "color": "rgba(11, 11, 11, 0.35)"},
                name="Satellite pixels",
                hoverinfo="skip",
            ),
            go.Scattermap(
                lon=lons,
                lat=lats,
                mode="lines",
                fill="toself",
                fillcolor="rgba(235, 104, 52, 0.12)",
                line={"width": 2, "color": COLOURS["heatwave_dark"]},
                name="MPA boundary",
                hovertemplate=f"{mpa['name']}<br>{mpa['area_km2']} km²<extra></extra>",
            ),
            go.Scattermap(
                lon=[station["lon"]],
                lat=[station["lat"]],
                mode="markers",
                marker={"size": 11, "color": COLOURS["sst"]},
                name="SOCIB station",
                hovertemplate=f"{station['name']}<extra></extra>",
            ),
        ]
    )
    base_map(fig, lons, lats, zoom=8.0, height=330)
    st.plotly_chart(fig, config=MAP_CONFIG)
    st.caption(
        f"Orange: the {mpa['area_km2']} km² park (WDPA {mpa['wdpa_id']}). Grid: the "
        f"{mpa['pixels']} satellite pixels of 0.05° inside it. Blue dot: the SOCIB "
        "station, moored in the park."
    )

# How to read it
with st.container(border=True):
    st.subheader("What is a marine heatwave?")
    method = meta["method"]
    st.markdown(
        f"A period of at least **{method['min_duration']} days** during which the sea "
        f"stays warmer than the **{method['percentile']}th percentile** of what is "
        f"usual for that day of the year ({method['reference']}). Here, *usual* is "
        f"the {method['climatology'][0]}-{method['climatology'][1]} climatology of "
        "the MPA-mean satellite SST. The category (Moderate, Strong, Severe, "
        "Extreme) says how many times the gap between threshold and climatology "
        "the peak reaches."
    )
    st.page_link(
        "year_explorer.py",
        label="Explore a year: map per pixel, daily SST, what-if warming",
        icon=":material/arrow_forward:",
    )
    st.page_link(
        "trends.py",
        label="Trends & what-if: any warming, any period, and the SST trend",
        icon=":material/arrow_forward:",
    )
    st.page_link(
        "validation.py",
        label="Validation: the satellite against the SOCIB station",
        icon=":material/arrow_forward:",
    )
    st.page_link(
        "method.py",
        label="Method & data: sources, processing chain, limits",
        icon=":material/arrow_forward:",
    )

footer(meta)
