"""Method & data: sources, processing chain, detection method and how to reuse
the outputs. Parameters are read from meta.json, so the text follows the build.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import CODE_URL, COLOURS, fetch, footer, style

meta = fetch("/meta")
method = meta["method"]
baseline = f"{method['climatology'][0]}-{method['climatology'][1]}"

st.title("Method & data")
st.markdown(
    "How the numbers in this dashboard are produced, from the raw sources to the "
    "API, and what they can and cannot say."
)

with st.container(border=True):
    st.subheader("Processing chain")
    st.graphviz_chart(
        """
        digraph {
            rankdir=LR; bgcolor="transparent";
            node [shape=box, style="rounded,filled", fillcolor="#fcfcfb",
                  color="#c3c2b7", fontname="sans-serif", fontsize=11];
            edge [color="#898781"];
            cmems [label="Copernicus Marine\\nMED SST L4\\nREP + NRT"];
            socib [label="SOCIB THREDDS\\nStation Cabrera\\n1, 13, 16.7 m"];
            osm [label="OpenStreetMap\\nMPA boundary"];
            raw [label="data/raw\\nas downloaded", shape=cylinder];
            processed [label="data/processed\\nZarr cube, CF NetCDF,\\nGeoJSON",
                       shape=cylinder];
            analysis [label="analysis\\nclimatology, threshold,\\nevents, scenarios"];
            exports [label="data/exports\\nParquet tables,\\nmeta.json, STAC",
                     shape=cylinder];
            api [label="FastAPI + DuckDB\\nSQL queries,\\nscenarios on demand",
                 fillcolor="#fde4d8"];
            dashboard [label="This dashboard", fillcolor="#fde4d8"];
            {cmems socib osm} -> raw -> processed -> analysis -> exports -> api
                -> dashboard;
        }
        """,
        width="stretch",
    )
    st.caption(
        "`make update` appends the new satellite days to the Zarr store instead "
        "of rebuilding 44 years. The same queries serve the API and this dashboard."
    )

with st.container(border=True):
    st.subheader("Data sources")
    mpa = meta["mpa"]
    st.markdown(
        "| Source | Provider | Product | Content | Terms |\n"
        "|---|---|---|---|---|\n"
        "| Satellite SST | Copernicus Marine Service | "
        "`SST_MED_SST_L4_REP_OBSERVATIONS_010_021`, then "
        "`SST_MED_SST_L4_NRT_OBSERVATIONS_010_004` | Daily L4 foundation SST, "
        "0.05°, 1982 to today | Copernicus Marine licence, attribution required |\n"
        "| In situ temperature | SOCIB | Station Cabrera moorings, L1, "
        "thredds.socib.es | Sea water temperature at 1, 13 and 16.7 m, with QC "
        "flags | CC BY 4.0 |\n"
        f"| MPA boundary | OpenStreetMap contributors | Relation "
        f"{mpa['osm_relation']} (WDPA {mpa['wdpa_id']}) | {mpa['name']}, "
        f"{mpa['area_km2']} km² | ODbL |"
    )

left, right = st.columns(2)

with left.container(border=True, height="stretch"):
    st.subheader("Marine heatwave detection")
    st.markdown(
        f"Definition of {method['reference']}, run on the MPA-mean series and, "
        "separately, on every pixel:\n"
        f"- **Climatology and threshold**: for each day of the year, the mean and "
        f"the {method['percentile']}th percentile of {baseline}, pooled over "
        f"±{method['window_half_width']} days and smoothed over "
        f"{method['smooth_width']} days.\n"
        f"- **Event**: at least {method['min_duration']} consecutive days above "
        f"the threshold; events separated by {method['max_gap']} days or fewer are "
        "merged.\n"
        "- **Category**: peak departure from climatology divided by the gap "
        "between threshold and climatology: 1-2× Moderate, 2-3× Strong, "
        "3-4× Severe, 4× or more Extreme (Hobday et al., 2018).\n"
        "- **What-if**: the observed series is shifted by a uniform warming and "
        "compared with the unchanged threshold.\n\n"
        "The implementation is checked against the reference code "
        "(ecjoliver/marineHeatWaves): identical events, start, duration, "
        "intensity and category."
    )

with right.container(border=True, height="stretch"):
    st.subheader("Joining reprocessed and near-real-time SST")
    corrections = pd.DataFrame(
        [
            {"month": int(m), "bias": float(b)}
            for m, b in (
                part.split(": ") for part in meta["nrt_bias_correction"].split(", ")
            )
        ]
    )
    overlap = meta.get("nrt_bias_overlap_days")
    st.markdown(
        "The reprocessed product (REP) gives the long record; the near-real-time "
        "product (NRT) extends it to today. NRT is regridded to the REP grid and "
        "corrected by the mean difference between REP and NRT of each calendar month"
        + (f", over {overlap / 365:.0f} years of overlap." if overlap else ".")
    )
    fig = go.Figure(
        go.Bar(
            x=pd.to_datetime(corrections.month, format="%m").dt.strftime("%b"),
            y=corrections.bias,
            marker_color=[
                COLOURS["heatwave"] if b > 0 else COLOURS["sst"]
                for b in corrections.bias
            ],
            hovertemplate="%{x}: %{y:+.3f} °C<extra></extra>",
        )
    )
    fig.update_yaxes(title="correction (°C)", zeroline=True)
    st.plotly_chart(style(fig, 220), config={"displayModeBar": False})
    st.caption(meta["sst_source"])

left, right = st.columns(2)

with left.container(border=True, height="stretch"):
    st.subheader("Reusing the outputs")
    st.markdown(
        "- **API**: interactive documentation at `/docs` on the API server "
        "(`make api` runs it locally). Routes for yearly and daily indicators, "
        "events, the "
        "pixel grid, validation, and `/scenario` for any warming over any window.\n"
        "- **Tables**: Parquet files in `data/exports/parquet` (daily, yearly, "
        "events, pixels, validation), readable by pandas, DuckDB or R.\n"
        "- **Catalogue**: a STAC catalog in `data/exports/stac` describes the "
        "series and the indicators with their extents, licences and providers.\n"
        "- **Provenance**: `meta.json` records the sources, the method parameters "
        "and the in-situ exclusions of each build.\n"
        f"- **Code**: [{CODE_URL.removeprefix('https://')}]({CODE_URL}); "
        "`make data` downloads and harmonises the sources, `make build` recomputes "
        "every indicator."
    )

with right.container(border=True, height="stretch"):
    st.subheader("Limits")
    st.markdown(
        f"- The baseline is fixed at {baseline}: part of the recent rise in "
        "heatwave days is the background warming itself, which a moving baseline "
        "would remove.\n"
        "- The MPA series averages the pixels before detection; the pixel map "
        "detects first, so the two can disagree on short, patchy events.\n"
        "- Satellite SST describes the surface layer only, while the seagrass "
        "meadows grow down to tens of metres; in summer the 16.7 m sensor reads "
        "almost 2 °C below the satellite.\n"
        "- Pixels touching the island mix sea and coast, and a pixel is counted "
        "in the MPA when its centre is inside the boundary."
    )

footer(meta)
