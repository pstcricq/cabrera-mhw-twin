# API

A FastAPI service over `data/exports`. Precomputed indicators are read from the Parquet tables with DuckDB SQL, filtered by the query parameters; `/scenario` runs the detection again on demand.

```bash
make api          # http://localhost:8000, interactive documentation at /docs
```

!!! tip "Try it in the browser"

    The root path redirects to `/docs`, the interactive OpenAPI documentation, where every route can be tried from the browser. The machine-readable schema is at `/openapi.json`.

## Routes

| Route | Parameters | Answer |
|---|---|---|
| `GET /health` | | Liveness probe, and whether the exports exist |
| `GET /meta` | | `meta.json`: provenance, method, current event, exclusions |
| `GET /mpa` | | The park boundary, GeoJSON Feature |
| `GET /indicators/yearly` | `start`, `end` (years), `delta` (°C, default 0), `min_days` | One row per year: heatwave days, summer days, share of the MPA, SST mean, cumulative intensity |
| `GET /indicators/daily` | `year`, or `start` and `end` (YYYY-MM-DD) | One row per day: SST, climatology, threshold, heatwave flag, share of the MPA |
| `GET /events` | `min_duration`, `category`, `since`, `order_by` (`start`, `duration`, `intensity_max`, `intensity_cumulative`), `limit` (1 to 1000, default 100) | Observed events, sorted descending |
| `GET /grid` | `year` (required), `delta`, `in_mpa` | Heatwave days per pixel for a year and a precomputed warming |
| `GET /scenario` | `delta` (0 to 5 °C, required), `start`, `end` | Detection re-run on the warmed MPA-mean series: total and per-year heatwave days |
| `GET /validation` | | Per sensor depth: days compared, bias, RMSE, correlation |
| `GET /validation/daily` | `depth` (m) | Daily station and satellite SST |

Errors follow HTTP: 404 when a window holds no data or a warming was not precomputed for `/grid`, 422 when a parameter is invalid, 503 when the exports have not been built.

## Examples

=== "curl"

    ```bash
    # Years with at least 150 heatwave days
    curl "http://localhost:8000/indicators/yearly?min_days=150"

    # The five strongest events since 2020
    curl "http://localhost:8000/events?since=2020-01-01&order_by=intensity_max&limit=5"

    # Summer 2003 in a sea 0.8 °C warmer
    curl "http://localhost:8000/scenario?delta=0.8&start=2003-06-01&end=2003-09-30"
    ```

=== "Python"

    ```python
    import pandas as pd
    import requests

    api = "http://localhost:8000"
    yearly = requests.get(f"{api}/indicators/yearly", params={"delta": 1}).json()
    grid = requests.get(f"{api}/grid", params={"year": 2025, "in_mpa": True}).json()
    yearly, grid = pd.DataFrame(yearly), pd.DataFrame(grid)
    ```

=== "In-process"

    ```python
    # The routes are plain functions: no server needed
    from cabrera_twin import api

    api.yearly(start=2016, end=2025)
    api.scenario(delta=1.5, start="1991-01-01", end="2020-12-31")["mhw_days"]
    ```

=== "DuckDB on the files"

    ```sql
    -- The same tables the API reads, queried directly
    SELECT year, mhw_days, area_percent
    FROM 'data/exports/parquet/yearly.parquet'
    WHERE delta = 1 AND year >= 2016
    ORDER BY year;
    ```

## Implementation notes

- Parameters are declared with `Annotated`, so each route is also a Python function with working defaults. The dashboard relies on it to run without a server.
- SQL values are passed as DuckDB parameters (`$name`), never formatted into the query; the only formatted parts are table paths and the `order_by` column, which the route restricts to a fixed list.
- `/meta` and the daily table used by `/scenario` are cached for the life of the process: restart the API after `make build`.
