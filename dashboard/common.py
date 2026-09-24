"""Data access, colours and chart helpers shared by the dashboard pages.

Every number comes from the API routes: over HTTP when CABRERA_API_URL is set,
otherwise by calling the route functions directly.
"""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from cabrera_twin import api

API_URL = os.environ.get("CABRERA_API_URL", "").rstrip("/")
ROUTES = {
    "/meta": api.meta,
    "/mpa": api.mpa_boundary,
    "/indicators/yearly": api.yearly,
    "/indicators/daily": api.daily,
    "/events": api.events,
    "/scenario": api.scenario,
    "/grid": api.grid,
    "/validation": api.validation,
    "/validation/daily": api.validation_daily,
}

COLOURS = {
    "sst": "#2a78d6",
    "climatology": "#898781",
    "threshold": "#52514e",
    "heatwave": "#eb6834",
    "heatwave_light": "#f39f78",
    "heatwave_dark": "#c94f1f",
    "heatwave_wash": "rgba(235, 104, 52, 0.28)",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "text": "#0b0b0b",
}
HEAT_COLOURS = [
    [253, 228, 216],
    [249, 195, 168],
    [243, 159, 120],
    [235, 104, 52],
    [201, 79, 31],
    [156, 58, 20],
    [110, 40, 12],
]
# Badge colours for the Hobday et al. (2018) categories
HEAT_SCALE = [
    [i / (len(HEAT_COLOURS) - 1), f"rgb({r}, {g}, {b})"]
    for i, (r, g, b) in enumerate(HEAT_COLOURS)
]
CATEGORY_COLOURS = {
    "Moderate": "yellow",
    "Strong": "orange",
    "Severe": "red",
    "Extreme": "violet",
}
# Esri Ocean basemap: bathymetry, no key needed, tiles stop at zoom 11 here
OCEAN_TILES = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/"
    "World_Ocean_Base/MapServer/tile/{z}/{y}/{x}"
)
OCEAN_ATTRIBUTION = "Basemap © Esri, GEBCO, NOAA"
SOURCES = (
    "Generated using E.U. Copernicus Marine Service Information · In situ data: "
    "SOCIB (CC BY 4.0) · MPA boundary © OpenStreetMap contributors (ODbL)"
)
CODE_URL = "https://github.com/pstcricq/cabrera-mhw-twin"
DOCS_URL = "https://pstcricq.github.io/cabrera-mhw-twin/"


@st.cache_data(ttl=600)
def fetch(route: str, **params):
    """Answer of one API route, over HTTP or in-process."""
    if API_URL:
        response = requests.get(f"{API_URL}{route}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    return ROUTES[route](**params)


def table(route: str, **params) -> pd.DataFrame:
    frame = pd.DataFrame(fetch(route, **params))
    for column in ("date", "start", "end"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column])
    return frame


def fmt_date(value) -> str:
    return pd.Timestamp(value).strftime("%-d %b %Y")


def style(fig: go.Figure, height: int) -> go.Figure:
    """Common chart frame: no title, thin grid, compact margins."""
    fig.update_layout(
        height=height,
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        hoverlabel={"bgcolor": "white", "font_size": 13},
        legend={"orientation": "h", "y": 1.08, "x": 0, "title": None},
        bargap=0.15,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=COLOURS["grid"], zeroline=False)
    return fig


def heat_chart(
    dates, value, threshold, normal, label: str, fmt: str, height: int = 110
) -> go.Figure:
    """Small chart for the headline cards: the series, the threshold (dashed), the
    normal (dotted), and the heatwave wash where the series is above the threshold.
    """
    above = np.maximum(value, threshold)
    hover = f"%{{y:{fmt}}} °C"
    fig = go.Figure(
        [
            go.Scatter(
                x=dates,
                y=normal,
                name="Normal",
                line={"color": COLOURS["climatology"], "width": 1, "dash": "dot"},
                hovertemplate=hover,
            ),
            go.Scatter(
                x=dates,
                y=threshold,
                name="Threshold",
                line={"color": COLOURS["threshold"], "width": 1, "dash": "dash"},
                hovertemplate=hover,
            ),
            go.Scatter(
                x=dates,
                y=above,
                fill="tonexty",
                fillcolor=COLOURS["heatwave_wash"],
                line={"width": 0},
                hoverinfo="skip",
                showlegend=False,
            ),
            go.Scatter(
                x=dates,
                y=value,
                name=label,
                line={"color": COLOURS["sst"], "width": 2},
                hovertemplate=hover,
            ),
        ]
    )
    fig.update_layout(
        height=height,
        margin={"l": 0, "r": 0, "t": 4, "b": 0},
        showlegend=False,
        hovermode="x unified",
        hoverlabel={"bgcolor": "white", "font_size": 12},
        font={"size": 11},
    )
    fig.update_xaxes(
        showgrid=False, tickformat="%-d %b", nticks=4, hoverformat="%-d %b %Y"
    )
    fig.update_yaxes(
        gridcolor=COLOURS["grid"], zeroline=False, nticks=3, ticksuffix="°"
    )
    return fig


def mpa_ring() -> tuple[list, list]:
    """Longitudes and latitudes of the MPA boundary."""
    ring = fetch("/mpa")["geometry"]["coordinates"][0]
    return [x for x, _ in ring], [y for _, y in ring]


def base_map(fig: go.Figure, lons, lats, zoom: float, height: int) -> go.Figure:
    """Esri Ocean basemap centred on the given coordinates; captions name the layers."""
    fig.update_layout(
        map={
            "style": "white-bg",
            "layers": [
                {
                    "below": "traces",
                    "sourcetype": "raster",
                    "source": [OCEAN_TILES],
                    "sourceattribution": OCEAN_ATTRIBUTION,
                }
            ],
            "center": {
                "lon": (min(lons) + max(lons)) / 2,
                "lat": (min(lats) + max(lats)) / 2,
            },
            "zoom": zoom,
        },
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        showlegend=False,
    )
    return fig


MAP_CONFIG = {"scrollZoom": False, "displayModeBar": False}


def events_table(events: pd.DataFrame) -> None:
    """Heatwave events with readable columns and units."""
    st.dataframe(
        events[
            [
                "start",
                "end",
                "duration",
                "intensity_max",
                "intensity_mean",
                "intensity_cumulative",
                "category",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "start": st.column_config.DateColumn("Start", format="D MMM YYYY"),
            "end": st.column_config.DateColumn("End", format="D MMM YYYY"),
            "duration": st.column_config.NumberColumn("Days"),
            "intensity_max": st.column_config.NumberColumn(
                "Max intensity", format="+%.2f °C"
            ),
            "intensity_mean": st.column_config.NumberColumn(
                "Mean intensity", format="+%.2f °C"
            ),
            "intensity_cumulative": st.column_config.NumberColumn(
                "Cumulative", format="%.1f °C·days"
            ),
            "category": st.column_config.TextColumn("Category"),
        },
    )


def footer(meta: dict) -> None:
    st.divider()
    st.caption(
        f"Data up to {fmt_date(meta['last_date'])} · {SOURCES} · "
        f"[Documentation]({DOCS_URL}) · [Code]({CODE_URL})"
    )
