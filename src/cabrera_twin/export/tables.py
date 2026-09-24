"""The indicators written to data/exports.

meta.json holds the provenance, method and current status, a small nested
document. Every indicator is a flat Parquet table in exports/parquet, which the
API queries with SQL (DuckDB) and the dashboard reads through the API.
"""

import json
from datetime import UTC, datetime

import pandas as pd

from cabrera_twin import config
from cabrera_twin.analysis.indicators import Indicators
from cabrera_twin.ingest import insitu

INSTRUMENT_DEPTHS = {"temprec003": 1, "sbe37004": 13, "sbe37002": 16.7}


def _parquet(name: str, frame: pd.DataFrame) -> None:
    config.PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(config.PARQUET_DIR / f"{name}.parquet", index=False)


def write_meta(ind: Indicators, sst_attrs: dict) -> None:
    daily, events = ind.daily, ind.events
    last = daily.index[-1]
    current = events[-1] if events and events[-1].end == last else None
    meta = {
        "generated": datetime.now(UTC).isoformat(timespec="minutes"),
        "last_date": last.date().isoformat(),
        "mpa": {
            "name": config.MPA_NAME,
            "wdpa_id": config.MPA_WDPA_ID,
            "osm_relation": config.MPA_OSM_RELATION,
            "area_km2": config.MPA_AREA_KM2,
            "pixels": ind.pixels,
        },
        "station": config.SOCIB_STATION,
        "method": {
            "reference": "Hobday et al. (2016, 2018)",
            "climatology": [config.CLIM_START[:4], config.CLIM_END[:4]],
            "percentile": config.PCTILE,
            "window_half_width": config.WINDOW_HALF_WIDTH,
            "smooth_width": config.SMOOTH_WIDTH,
            "min_duration": config.MIN_DURATION,
            "max_gap": config.MAX_GAP,
        },
        "sst_source": sst_attrs.get("source", "unknown"),
        "nrt_bias_correction": sst_attrs.get("nrt_bias_correction_degC", ""),
        "nrt_bias_overlap_days": sst_attrs.get("nrt_bias_overlap_days"),
        "insitu": {
            "qc_flags": list(insitu.GOOD_FLAGS),
            "min_day_coverage": config.MIN_DAY_COVERAGE,
        },
        "scenarios": [f"{d:g}" for d in (0.0, *config.SCENARIO_DELTAS)],
        "summer_months": list(config.SUMMER_MONTHS),
        "current_event": current.as_dict() if current else None,
        "insitu_excluded": [
            {"depth": insitu_depth, "start": s, "end": e, "reason": why}
            for name, rules in config.SOCIB_EXCLUDE.items()
            for insitu_depth in [INSTRUMENT_DEPTHS[name]]
            for s, e, why in rules
        ],
    }
    config.META_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.META_FILE.write_text(json.dumps(meta, separators=(",", ":")))


def write_parquet(ind: Indicators) -> None:
    daily, area = ind.daily, ind.area
    _parquet(
        "daily",
        pd.DataFrame(
            {
                "date": daily.index,
                # stored unrounded: /scenario re-runs the detection on them
                "sst": daily.sst,
                "climatology": daily.seas,
                "threshold": daily.thresh,
                "mhw": daily.mhw,
                "area_percent": area["fraction"],
            }
        ),
    )
    rows = []
    for year, row in ind.yearly.iterrows():
        for delta in ind.scenarios.columns:
            rows.append(
                {
                    "year": int(year),
                    "delta": float(delta),
                    "mhw_days": int(ind.scenarios.loc[year, delta]),
                    "summer_mhw_days": int(ind.summer.loc[year, delta]),
                    "area_percent": area["yearly_mean"][delta][str(int(year))],
                    "n_days": int(row.n_days),
                    "sst_mean": round(row.sst_mean, 2),
                    "intensity_cumulative": round(row.intensity_cumulative, 1),
                }
            )
    _parquet("yearly", pd.DataFrame(rows))
    _parquet("events", pd.DataFrame([e.as_dict() for e in ind.events]))
    grid = ind.grid
    pixels = [
        {
            "year": int(year),
            "delta": float(delta),
            "latitude": grid["latitude"][i],
            "longitude": grid["longitude"][j],
            "in_mpa": bool(grid["in_mpa"][i][j]),
            "mhw_days": int(days),
        }
        for delta, years in grid["mhw_days"].items()
        for year, table in years.items()
        for i, row in enumerate(table)
        for j, days in enumerate(row)
        if days >= 0
    ]
    _parquet("pixels", pd.DataFrame(pixels))
    _parquet("validation", ind.validation)
