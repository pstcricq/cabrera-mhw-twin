"""Trends and what-if: how heatwave days respond to any uniform warming, and how
the MPA itself has warmed since 1982.

The warming and the period live in the URL. Every value of the slider is a new
detection run by the /scenario route, not a lookup in precomputed tables.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import COLOURS, events_table, fetch, footer, style, table

STEP = 0.1
MAX_WARMING = 3.0

meta = fetch("/meta")
yearly = table("/indicators/yearly")
complete = yearly[yearly.n_days >= 365]
years = complete.year.tolist()

params = st.query_params
try:
    default_warming = float(params.get("warming", 1.0))
except ValueError:
    default_warming = 1.0
default_start = int(params.get("start", 1991))
default_end = int(params.get("end", 2020))

st.title("Trends & what-if")
st.markdown(
    "Add a uniform warming to the observed series and count again the days above "
    "the unchanged 1991-2020 threshold. It answers *how often would the same "
    "variability cross today's threshold in a warmer sea*, a sensitivity test "
    "rather than a climate projection."
)

pick_warming, pick_years = st.columns(2)
warming = pick_warming.slider(
    "Uniform warming",
    0.0,
    MAX_WARMING,
    value=min(max(default_warming, 0.0), MAX_WARMING),
    step=STEP,
    format="+%.1f °C",
)
start, end = pick_years.select_slider(
    "Years",
    options=years,
    value=(
        default_start if default_start in years else years[0],
        default_end if default_end in years else years[-1],
    ),
)
st.query_params.update(
    {"warming": f"{warming:g}", "start": str(start), "end": str(end)}
)
window = {"start": f"{start}-01-01", "end": f"{end}-12-31"}
n_years = end - start + 1


def run(delta: float) -> dict:
    return fetch("/scenario", delta=float(round(delta, 2)), **window)


observed = run(0.0)
warmed = run(warming)
obs_mean = observed["mhw_days"] / n_years
warm_mean = warmed["mhw_days"] / n_years
share = 100 * warmed["mhw_days"] / warmed["days_in_window"]
obs_share = 100 * observed["mhw_days"] / observed["days_in_window"]

# The window in three figures
first, second, third = st.columns(3)
first.metric(
    f"Heatwave days per year, {start}-{end}",
    f"{obs_mean:.1f}",
    delta="observed",
    delta_color="off",
    delta_arrow="off",
    border=True,
    height="stretch",
)
second.metric(
    f"Same years at +{warming:.1f} °C",
    f"{warm_mean:.1f}",
    delta=(
        f"×{warm_mean / obs_mean:.1f} vs observed"
        if obs_mean
        else f"{warm_mean - obs_mean:+.1f} days vs observed"
    ),
    delta_color="inverse" if warming else "off",
    delta_arrow="off",
    border=True,
    height="stretch",
)
third.metric(
    "Share of days in heatwave",
    f"{share:.0f} %",
    delta=f"{share - obs_share:+.0f} points vs observed" if warming else "observed",
    delta_color="inverse" if warming else "off",
    delta_arrow="off",
    border=True,
    height="stretch",
)

# Year by year
with st.container(border=True):
    st.subheader("Heatwave days per year, observed and warmed")
    per_year = pd.DataFrame(observed["years"]).merge(
        pd.DataFrame(warmed["years"]), on="year", suffixes=("_observed", "_warmed")
    )
    fig = go.Figure(
        [
            go.Bar(
                x=per_year.year,
                y=per_year.mhw_days_observed,
                name="Observed",
                marker_color=COLOURS["heatwave_dark"],
                hovertemplate="%{y} days observed<extra></extra>",
            ),
            go.Bar(
                x=per_year.year,
                y=per_year.mhw_days_warmed,
                name=f"+{warming:.1f} °C",
                marker_color=COLOURS["heatwave_light"],
                hovertemplate=f"%{{y}} days at +{warming:.1f} °C<extra></extra>",
            ),
        ]
    )
    fig.update_layout(barmode="group", hovermode="x unified")
    fig.update_yaxes(title="days", range=[0, 366])
    st.plotly_chart(style(fig, 300), config={"displayModeBar": False})

response, trend = st.columns(2)

# How the count responds to warming
with response.container(border=True, height="stretch"):
    st.subheader("Response to warming")
    deltas = np.round(np.arange(0, MAX_WARMING + STEP / 2, STEP), 2)
    curve = [run(d)["mhw_days"] / n_years for d in deltas]
    fig = go.Figure(
        [
            go.Scatter(
                x=deltas,
                y=curve,
                mode="lines",
                line={"color": COLOURS["heatwave"], "width": 2.5},
                hovertemplate="+%{x:.1f} °C: %{y:.0f} days per year<extra></extra>",
            ),
            go.Scatter(
                x=[warming],
                y=[warm_mean],
                mode="markers",
                marker={"size": 11, "color": COLOURS["heatwave_dark"]},
                hovertemplate="+%{x:.1f} °C: %{y:.0f} days per year<extra></extra>",
            ),
        ]
    )
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title="uniform warming (°C)", ticksuffix="", showgrid=True)
    fig.update_yaxes(title="heatwave days per year", range=[0, 366])
    st.plotly_chart(style(fig, 300), config={"displayModeBar": False})
    st.caption(
        f"Mean over {start}-{end}. The curve flattens as the year fills up: "
        "beyond some warming almost every day is above the threshold."
    )

# How the MPA has warmed
with trend.container(border=True, height="stretch"):
    st.subheader("Mean sea surface temperature")
    slope, intercept = np.polyfit(complete.year, complete.sst_mean, 1)
    fit = intercept + slope * complete.year
    fig = go.Figure(
        [
            go.Scatter(
                x=complete.year,
                y=complete.sst_mean,
                mode="lines+markers",
                line={"color": COLOURS["sst"], "width": 1.5},
                marker={"size": 5},
                name="Yearly mean",
                hovertemplate="%{x}: %{y:.2f} °C<extra></extra>",
            ),
            go.Scatter(
                x=complete.year,
                y=fit,
                mode="lines",
                line={"color": COLOURS["threshold"], "dash": "dash", "width": 1.5},
                name="Linear trend",
                hoverinfo="skip",
            ),
        ]
    )
    fig.add_vrect(
        x0=start - 0.5,
        x1=end + 0.5,
        fillcolor=COLOURS["grid"],
        opacity=0.4,
        line_width=0,
    )
    fig.update_layout(showlegend=False)
    fig.update_yaxes(ticksuffix=" °C")
    st.plotly_chart(style(fig, 300), config={"displayModeBar": False})
    st.caption(
        f"MPA-mean satellite SST per complete year: **{slope * 10:+.2f} °C per "
        f"decade** since {years[0]} (least-squares fit). The shaded band is the "
        "period used on the left."
    )

with st.container(border=True):
    st.subheader(f"Largest heatwaves since {years[0]}")
    events_table(table("/events", order_by="intensity_cumulative", limit=10))
    st.caption(
        "Observed events on the MPA-mean series, ranked by cumulative intensity "
        "(°C·days above climatology), whatever the period chosen above."
    )

with st.container(border=True):
    st.subheader("Reading a what-if")
    st.markdown(
        "- The threshold stays the 90th percentile of 1991-2020: the question is "
        "how an ecosystem adapted to that climate would experience a warmer sea.\n"
        "- The whole series is shifted, so the day-to-day and year-to-year "
        "variability is the observed one; a real warmer climate may also change "
        "the variability.\n"
        "- Any warming and any period can be asked for, here or through the API: "
        f"`/scenario?delta={warming:g}&start={window['start']}&end={window['end']}`."
    )

footer(meta)
