"""Validation: the satellite series against the SOCIB station moored in the MPA."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import COLOURS, fetch, fmt_date, footer, style, table

DEPTH_COLOURS = ["#1baf7a", "#eb6834", "#8e5bd0", "#898781"]

meta = fetch("/meta")
station = meta["station"]
stats = table("/validation")
series = table("/validation/daily")
depths = stats.depth_m.tolist()
colour = dict(zip(depths, DEPTH_COLOURS, strict=False))
satellite = series.drop_duplicates("date")[["date", "satellite_sst"]]

st.title("Validation")
st.markdown(
    f"The satellite series is checked against the **{station['name']}**, moored "
    "inside the park: the satellite value of the pixel that contains the station, "
    "against the daily mean of each SOCIB temperature sensor."
)

# One card per sensor depth
for column, s in zip(st.columns(len(stats)), stats.itertuples(), strict=True):
    column.metric(
        f"Sensor at {s.depth_m:g} m",
        f"r = {s.r:.2f}",
        delta=f"bias {s.bias:+.2f} °C · RMSE {s.rmse:.2f} °C",
        delta_color="off",
        delta_arrow="off",
        delta_description=f"{s.n_days} days",
        border=True,
        height="stretch",
        help="Bias is in situ minus satellite; r is the Pearson correlation of "
        "the daily values over the days both exist.",
    )

left, right = st.columns([1.6, 1])

with left.container(border=True, height="stretch"):
    st.subheader("Daily temperature at the station")
    traces = [
        go.Scatter(
            x=satellite.date,
            y=satellite.satellite_sst,
            name="Satellite (station pixel)",
            line={"color": COLOURS["sst"], "width": 2},
            hovertemplate="%{y:.2f} °C",
        )
    ]
    for depth in depths:
        at = series[series.depth_m == depth]
        traces.append(
            go.Scatter(
                x=at.date,
                y=at.station_sst,
                name=f"Sensor {depth:g} m",
                line={"color": colour[depth], "width": 1.5},
                hovertemplate="%{y:.2f} °C",
            )
        )
    fig = go.Figure(traces)
    style(fig, 380)
    fig.update_layout(
        hovermode="x unified",
        margin={"l": 40, "r": 0, "t": 8, "b": 0},
        legend={"orientation": "h", "y": -0.12, "yanchor": "top", "x": 0},
    )
    fig.update_xaxes(hoverformat="%-d %b %Y")
    fig.update_yaxes(ticksuffix=" °C")
    st.plotly_chart(fig, config={"displayModeBar": False})

with right.container(border=True, height="stretch"):
    st.subheader("Sensor against satellite")
    both = series.dropna()
    low = np.floor(min(both.station_sst.min(), both.satellite_sst.min()))
    high = np.ceil(max(both.station_sst.max(), both.satellite_sst.max()))
    fig = go.Figure(
        [
            go.Scatter(
                x=[low, high],
                y=[low, high],
                mode="lines",
                line={"color": COLOURS["climatology"], "dash": "dot", "width": 1},
                name="1:1",
                hoverinfo="skip",
            )
        ]
        + [
            go.Scatter(
                x=both[both.depth_m == depth].satellite_sst,
                y=both[both.depth_m == depth].station_sst,
                mode="markers",
                marker={"size": 5, "color": colour[depth], "opacity": 0.7},
                name=f"{depth:g} m",
                customdata=both[both.depth_m == depth].date.dt.strftime("%-d %b %Y"),
                hovertemplate=(
                    "%{customdata}<br>satellite %{x:.2f} °C<br>"
                    f"sensor {depth:g} m " + "%{y:.2f} °C<extra></extra>"
                ),
            )
            for depth in depths
        ]
    )
    style(fig, 380)
    fig.update_layout(
        margin={"l": 40, "r": 0, "t": 8, "b": 0},
        legend={"orientation": "h", "y": -0.18, "yanchor": "top", "x": 0},
    )
    fig.update_xaxes(title="satellite (°C)", range=[low, high], showgrid=True)
    fig.update_yaxes(title="sensor (°C)", range=[low, high], scaleanchor="x")
    st.plotly_chart(fig, config={"displayModeBar": False})

with st.container(border=True):
    st.subheader("Reading the comparison")
    flags = " and ".join(str(f) for f in meta["insitu"]["qc_flags"])
    coverage = meta["insitu"]["min_day_coverage"]
    notes = [
        "The satellite product is a foundation SST: the temperature just below the "
        "surface, free of the afternoon skin warming. The sensors sit deeper, so a "
        "negative bias grows with depth when the water column is stratified in "
        "summer, which is what the 16.7 m sensor shows.",
        "A 0.05° pixel covers about 25 km² while the station is a single point, "
        "and the pixels next to the island mix sea and coast.",
        f"In situ values keep the SOCIB quality flags {flags}, and a day counts "
        f"only if at least {coverage:.0%} of its expected measurements exist.",
    ]
    for rule in meta["insitu_excluded"]:
        until = f" to {fmt_date(rule['end'])}" if rule["end"] else ""
        notes.append(
            f"Excluded after inspection: the {rule['depth']:g} m sensor from "
            f"{fmt_date(rule['start'])}{until} ({rule['reason']})."
        )
    st.markdown("\n".join(f"- {n}" for n in notes))
    first = pd.Timestamp(series.date.min())
    st.caption(
        f"Station series from {fmt_date(first)}; "
        "source: SOCIB data centre, thredds.socib.es."
    )

footer(meta)
