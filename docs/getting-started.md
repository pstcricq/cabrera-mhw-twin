# Getting started

## Requirements

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/), which creates the environment from the pinned `uv.lock`.
- `make`, for the shortcuts below (`make help` lists them).
- A free [Copernicus Marine](https://marine.copernicus.eu) account, only to download the satellite data again. The processed series and the exports are committed, so the API, the dashboard and `make build` work without it.
- Docker, only for `make up`.

## Install

```bash
git clone https://github.com/pstcricq/cabrera-mhw-twin.git
cd cabrera-mhw-twin
make install     # uv sync: runtime and development dependencies
make hooks       # optional: pre-commit hooks (ruff, file checks)
```

!!! tip "No account needed to run it"

    The processed series and the indicators are committed with the code: the API, the dashboard and `make build` work right after `make install`. A Copernicus Marine account is only needed to download the satellite data again.

## Run the services

```bash
make api         # FastAPI on http://localhost:8000, interactive docs at /docs
make dashboard   # Streamlit on http://localhost:8501
```

The dashboard calls the API functions directly. To make it go through HTTP instead, point it at a running API:

```bash
CABRERA_API_URL=http://localhost:8000 make dashboard
```

`make up` builds one Docker image and starts both services with Compose, the dashboard reading the API over the Compose network. `make down` stops them.

## Refresh the data

```bash
uv run copernicusmarine login   # once per machine, stores the credentials locally
make data                       # download every source again and harmonise it
make build                      # recompute the indicators into data/exports
```

`make update` is the daily path: it downloads only the satellite days published since the last run, appends them to the Zarr store, refreshes the station files and rebuilds the indicators.

| Command | Network | Time | Writes |
|---|---|---|---|
| `make data` | Copernicus, SOCIB, OpenStreetMap | under a minute | `data/raw`, `data/processed` |
| `make update` | Copernicus, SOCIB | seconds | appends to `data/processed`, then `data/exports` |
| `make build` | none | under 10 s | `data/exports` |

## Project layout

```text
src/cabrera_twin/
  config.py        study area, sources, method parameters
  ingest/          sst.py, insitu.py, mpa.py: sources to data/processed
  analysis/        mhw.py, whatif.py, indicators.py: the science, no file I/O
  export/          tables.py, stac.py: data/exports
  pipeline.py      the build step, chaining analysis and export
  api.py           FastAPI service over the exports
  cli.py           cabrera-twin fetch | update | build | all
dashboard/         Streamlit pages
data/
  raw/             as downloaded, one folder per provider (not versioned)
  processed/       harmonised series (Zarr, CF NetCDF, GeoJSON)
  exports/         Parquet tables, meta.json, STAC catalog
docs/              this documentation (MkDocs)
tests/             pytest suite
```

## Build this documentation

```bash
make docs        # live preview on http://localhost:8001
```

The CI builds it with `mkdocs build --strict`, so a broken link fails the build, and publishes it to GitHub Pages from the `main` branch.
