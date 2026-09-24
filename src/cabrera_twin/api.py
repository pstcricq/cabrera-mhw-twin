"""HTTP API over the Cabrera heatwave indicators.

Precomputed indicators are read from the Parquet exports with DuckDB SQL, filtered by
the query parameters. /scenario re-runs the heatwave detection on the daily series
for any warming and any date window. Parameters are declared with Annotated, so each
route is also a plain Python function with its defaults. Run it with `make api`.
"""

import json
from functools import lru_cache
from typing import Annotated

import duckdb
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse

from cabrera_twin import config
from cabrera_twin.analysis import mhw

app = FastAPI(
    title="Cabrera marine heatwave indicators",
    version="0.4.0",
    summary=(
        "Marine heatwave indicators for the Cabrera Archipelago National Park, "
        "from Copernicus Marine satellite SST validated against the SOCIB station."
    ),
)


def _table(name: str) -> str:
    """Path of a Parquet export, for use inside a SQL query."""
    path = config.PARQUET_DIR / f"{name}.parquet"
    if not path.exists():
        raise HTTPException(503, f"{name} not built yet: run `cabrera-twin build`")
    return f"read_parquet('{path}')"


def _query(sql: str, **params) -> list[dict]:
    frame = duckdb.execute(sql, params).df()
    return json.loads(frame.to_json(orient="records", date_format="iso"))


@lru_cache
def _daily() -> pd.DataFrame:
    """The daily series with its climatology, indexed by date."""
    frame = duckdb.execute(f"SELECT * FROM {_table('daily')}").df()
    return frame.set_index(pd.DatetimeIndex(frame.pop("date")))


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", summary="Liveness probe")
def health() -> dict:
    return {"status": "ok", "exports": config.EXPORT_DIR.exists()}


@app.get("/meta", summary="Provenance, method parameters and current status")
@lru_cache
def meta() -> dict:
    if not config.META_FILE.exists():
        raise HTTPException(503, "meta not built yet: run `cabrera-twin build`")
    return json.loads(config.META_FILE.read_text())


@app.get("/mpa", summary="Marine protected area boundary (GeoJSON)")
def mpa_boundary() -> dict:
    return json.loads(config.MPA_FILE.read_text())


@app.get("/indicators/yearly", summary="Heatwave days and intensity per year")
def yearly(
    start: Annotated[int | None, Query(description="First year, inclusive")] = None,
    end: Annotated[int | None, Query(description="Last year, inclusive")] = None,
    delta: Annotated[float, Query(description="Warming scenario, degrees C")] = 0,
    min_days: Annotated[
        int, Query(ge=0, description="Keep years with at least N days")
    ] = 0,
) -> list:
    return _query(
        f"""SELECT year, mhw_days, summer_mhw_days, area_percent, n_days, sst_mean,
                   intensity_cumulative
            FROM {_table("yearly")}
            WHERE delta = $delta
              AND ($start IS NULL OR year >= $start)
              AND ($end IS NULL OR year <= $end)
              AND mhw_days >= $min_days
            ORDER BY year""",
        delta=delta,
        start=start,
        end=end,
        min_days=min_days,
    )


@app.get("/indicators/daily", summary="Daily SST, climatology and heatwave flag")
def daily(
    year: Annotated[int | None, Query(description="Calendar year")] = None,
    start: Annotated[str | None, Query(description="First day, YYYY-MM-DD")] = None,
    end: Annotated[str | None, Query(description="Last day, YYYY-MM-DD")] = None,
) -> list:
    rows = _query(
        f"""SELECT date, sst, climatology, threshold, mhw, area_percent
            FROM {_table("daily")}
            WHERE ($year IS NULL OR year(date) = $year)
              AND ($start IS NULL OR date >= $start::DATE)
              AND ($end IS NULL OR date <= $end::DATE)
            ORDER BY date""",
        year=year,
        start=start,
        end=end,
    )
    if not rows:
        raise HTTPException(404, "no data for that window")
    return rows


@app.get("/events", summary="Detected marine heatwaves")
def events(
    min_duration: Annotated[
        int, Query(ge=0, description="Keep events of at least N days")
    ] = 0,
    category: Annotated[
        str | None, Query(description="Moderate, Strong, Severe or Extreme")
    ] = None,
    since: Annotated[
        str | None, Query(description="Keep events starting on or after this day")
    ] = None,
    order_by: Annotated[
        str, Query(pattern="^(start|duration|intensity_max|intensity_cumulative)$")
    ] = "intensity_cumulative",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list:
    return _query(
        f"""SELECT * FROM {_table("events")}
            WHERE duration >= $min_duration
              AND ($category IS NULL OR lower(category) = lower($category))
              AND ($since IS NULL OR start >= $since)
            ORDER BY {order_by} DESC
            LIMIT $limit""",
        min_duration=min_duration,
        category=category,
        since=since,
        limit=limit,
    )


@app.get("/scenario", summary="What-if: any uniform warming, computed on demand")
def scenario(
    delta: Annotated[
        float, Query(ge=0, le=5, description="Uniform warming, degrees C")
    ],
    start: Annotated[str | None, Query(description="First day, YYYY-MM-DD")] = None,
    end: Annotated[str | None, Query(description="Last day, YYYY-MM-DD")] = None,
) -> dict:
    """Detection re-run on the warmed series, against the unchanged threshold."""
    frame = _daily().loc[start:end]
    if frame.empty:
        raise HTTPException(404, "no data for that window")
    warmed = frame.rename(columns={"climatology": "seas", "threshold": "thresh"})
    warmed = warmed.assign(sst=warmed.sst + delta)
    flags = pd.Series(mhw.event_mask(warmed), index=frame.index)
    per_year = flags.groupby(flags.index.year).sum()
    return {
        "delta_degC": delta,
        "window": [str(frame.index[0].date()), str(frame.index[-1].date())],
        "note": (
            "Sensitivity test: the observed series is shifted by delta and compared "
            "with the unchanged baseline threshold. Not a climate projection."
        ),
        "mhw_days": int(flags.sum()),
        "days_in_window": int(len(flags)),
        "years": [{"year": int(y), "mhw_days": int(n)} for y, n in per_year.items()],
    }


@app.get("/validation", summary="Satellite against the SOCIB station, per depth")
def validation() -> list:
    """Bias (station - satellite), RMSE and correlation over the days both exist."""
    return _query(
        f"""SELECT depth_m,
                   count(*) AS n_days,
                   round(avg(station_sst - satellite_sst), 2) AS bias,
                   round(sqrt(avg((station_sst - satellite_sst) ^ 2)), 2) AS rmse,
                   round(corr(station_sst, satellite_sst), 2) AS r
            FROM {_table("validation")}
            WHERE station_sst IS NOT NULL AND satellite_sst IS NOT NULL
            GROUP BY depth_m
            ORDER BY depth_m"""
    )


@app.get("/validation/daily", summary="Daily station and satellite SST, per depth")
def validation_daily(
    depth: Annotated[float | None, Query(description="Sensor depth, m")] = None,
) -> list:
    return _query(
        f"""SELECT date, depth_m, station_sst, satellite_sst
            FROM {_table("validation")}
            WHERE $depth IS NULL OR depth_m = $depth
            ORDER BY depth_m, date""",
        depth=depth,
    )


@app.get("/grid", summary="Heatwave days per satellite pixel")
def grid(
    year: Annotated[int, Query(description="Calendar year")],
    delta: Annotated[float, Query(description="Warming scenario, degrees C")] = 0,
    in_mpa: Annotated[
        bool | None, Query(description="Restrict to the pixels inside the MPA")
    ] = None,
) -> list:
    rows = _query(
        f"""SELECT latitude, longitude, in_mpa, mhw_days
            FROM {_table("pixels")}
            WHERE year = $year AND delta = $delta
              AND ($in_mpa IS NULL OR in_mpa = $in_mpa)
            ORDER BY latitude, longitude""",
        year=year,
        delta=delta,
        in_mpa=in_mpa,
    )
    if not rows:
        raise HTTPException(
            404,
            f"no grid for year {year} and delta {delta}; "
            f"precomputed scenarios: {meta()['scenarios']}",
        )
    return rows
