# cabrera-mhw-twin

[![CI](https://github.com/pstcricq/cabrera-mhw-twin/actions/workflows/ci.yml/badge.svg)](https://github.com/pstcricq/cabrera-mhw-twin/actions/workflows/ci.yml) [![Docs](https://img.shields.io/badge/docs-MkDocs%20Material-eb6834)](https://pstcricq.github.io/cabrera-mhw-twin/) [![Python](https://img.shields.io/badge/python-3.12%2B-2a78d6)](pyproject.toml) [![Code licence: MIT](https://img.shields.io/badge/code%20licence-MIT-1baf7a)](LICENSE) [![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![Data: Copernicus Marine](https://img.shields.io/badge/data-Copernicus%20Marine-0b4f8a)](https://doi.org/10.48670/moi-00173) [![Data: SOCIB, CC BY 4.0](https://img.shields.io/badge/data-SOCIB%20%C2%B7%20CC%20BY%204.0-0b4f8a)](https://www.socib.es/en/what-we-do/metocean-data/data-terms-of-use) [![Data: OpenStreetMap, ODbL](https://img.shields.io/badge/data-OpenStreetMap%20%C2%B7%20ODbL-0b4f8a)](https://www.openstreetmap.org/copyright) [![STAC 1.1](https://img.shields.io/badge/STAC-1.1-898781)](data/exports/stac/catalog.json) [![Zarr](https://img.shields.io/badge/Zarr-v3-898781)](data/processed/sst_cabrera_daily.zarr)

Marine heatwave indicators for the **Cabrera Archipelago National Park** (Balearic Islands), a 909 km² marine protected area, built as a small component of a Digital Twin of the Ocean: satellite and in-situ ocean data in, reproducible indicators out, served through an HTTP API and an interactive dashboard.

- Daily satellite sea surface temperature since 1982 (Copernicus Marine), extended to today with the near-real-time product.
- Marine heatwaves after Hobday et al. (2016, 2018), over the park and pixel by pixel, checked event for event against the reference implementation.
- What-if scenarios for any uniform warming, computed on demand.
- Validation against the SOCIB Station Cabrera, moored inside the park.
- A FastAPI service over Parquet tables, a STAC catalog, and a five-page Streamlit dashboard.

![Overview page of the dashboard: the ongoing heatwave, today's sea surface temperature, heatwave days per year since 1982 and the park with its satellite pixels](docs/assets/screenshots/overview.png)

**Documentation:** [pstcricq.github.io/cabrera-mhw-twin](https://pstcricq.github.io/cabrera-mhw-twin/), the technical guide: architecture, data schemas, method, API reference.

## Install

Requires Python 3.12 or later, [uv](https://docs.astral.sh/uv/) and `make`.

```bash
git clone https://github.com/pstcricq/cabrera-mhw-twin.git
cd cabrera-mhw-twin
make install
```

The processed series and the indicators are committed: the API and the dashboard run right away, without any account.

## Use

```bash
make dashboard    # dashboard on http://localhost:8501
make api          # API on http://localhost:8000, interactive docs at /docs
make up           # both in Docker, the dashboard reading the API (make down to stop)
```

The dashboard has five pages: **Overview** (the ongoing heatwave, the long-term change), **Year explorer** (map per pixel and daily SST for any year), **Trends & what-if** (any warming, any period), **Validation** (satellite against the station) and **Method & data**.

![What-if: heatwave days per year over 1991-2020 as the uniform warming goes from 0 to 3 °C](docs/assets/screenshots/what-if.gif)

A few API calls:

```bash
curl "http://localhost:8000/indicators/yearly?min_days=150"       # years with 150+ heatwave days
curl "http://localhost:8000/events?since=2020-01-01&limit=5"      # strongest recent events
curl "http://localhost:8000/scenario?delta=0.8&start=2003-06-01&end=2003-09-30"
```

The same tables can be read without the API, in pandas, R or DuckDB:

```sql
SELECT year, mhw_days FROM 'data/exports/parquet/yearly.parquet' WHERE delta = 0;
```

## Refresh the data

Downloading the satellite data needs a free [Copernicus Marine](https://marine.copernicus.eu) account.

```bash
uv run copernicusmarine login    # once per machine
make update                      # add the days published since the last run, rebuild
make data                        # or download every source again
make build                       # recompute the indicators only
```

## Develop

```bash
make hooks        # pre-commit hooks
make check        # lint and tests
make docs         # documentation preview on http://localhost:8001
make help         # every target
```

## Project layout

```text
src/cabrera_twin/   ingest/ (sources), analysis/ (detection, scenarios, indicators),
                    export/ (Parquet, STAC), pipeline.py, api.py, cli.py, config.py
dashboard/          Streamlit pages
data/               raw/ (not versioned), processed/, exports/
docs/               documentation sources (MkDocs)
tests/              pytest suite
```

## Data and licences

The **code** is under the [MIT licence](LICENSE). The **data** in `data/` derive from third-party sources and remain under their terms:

- **Sea surface temperature**: generated using E.U. Copernicus Marine Service Information, products `SST_MED_SST_L4_REP_OBSERVATIONS_010_021` ([10.48670/moi-00173](https://doi.org/10.48670/moi-00173)) and `SST_MED_SST_L4_NRT_OBSERVATIONS_010_004` ([10.48670/moi-00172](https://doi.org/10.48670/moi-00172)), under the [Copernicus Marine Service licence](https://marine.copernicus.eu/user-corner/service-commitments-and-licence).
- **In situ temperature**: SOCIB, Balearic Islands Coastal Observing and Forecasting System, Station Cabrera mooring data ([thredds.socib.es](https://thredds.socib.es/thredds/catalog/mooring/catalog.html)), under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **MPA boundary**: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, under the ODbL; the boundary file in `data/processed` is a derived database under the same licence.
- **Basemap** of the dashboard maps: Esri, GEBCO, NOAA.

Details per file in the [documentation](https://pstcricq.github.io/cabrera-mhw-twin/data/#licences-and-attribution).

## References

- Hobday, A. J., et al. (2016). A hierarchical approach to defining marine heatwaves. _Progress in Oceanography_, 141, 227-238.
- Hobday, A. J., et al. (2018). Categorizing and naming marine heatwaves. _Oceanography_, 31(2), 162-173.
