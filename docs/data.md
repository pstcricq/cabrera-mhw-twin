# Data

## Sources

| Source | Provider | Product and access | Content |
|---|---|---|---|
| Satellite SST, long record | Copernicus Marine Service | `SST_MED_SST_L4_REP_OBSERVATIONS_010_021`, dataset `cmems_SST_MED_SST_L4_REP_OBSERVATIONS_010_021`, via the `copernicusmarine` toolbox ([10.48670/moi-00173](https://doi.org/10.48670/moi-00173)) | Reprocessed L4 foundation SST, daily, 0.05°, from 1 January 1982, a few weeks behind real time |
| Satellite SST, recent days | Copernicus Marine Service | `SST_MED_SST_L4_NRT_OBSERVATIONS_010_004`, dataset `SST_MED_SST_L4_NRT_OBSERVATIONS_010_004_a_V2` ([10.48670/moi-00172](https://doi.org/10.48670/moi-00172)) | Near-real-time L4 foundation SST, daily, 0.0625°, up to yesterday |
| In situ temperature | SOCIB | Monthly L1 NetCDF files of the Station Cabrera moorings, [thredds.socib.es](https://thredds.socib.es/thredds/catalog/mooring/catalog.html) | `WTR_TEM` with its QC flags, sensors at 1 m, 13 m and 16.7 m |
| MPA boundary | OpenStreetMap contributors | Relation 10036151 through the Nominatim lookup service | Polygon of the Parc Nacional de l'Arxipèlag de Cabrera (2019 extension), WDPA 196045 |

The extraction box is 38.85° to 39.35° N and 2.75° to 3.45° E: a 10 by 14 grid of REP pixels, 42 of them with their centre inside the park. The station, at 39.1507° N and 2.9310° E, lies inside the park.

## Layers

```text
data/
  raw/          as downloaded, not versioned
    copernicus/   sst_rep.nc, sst_nrt.nc
    socib/        depNNNN_station-cabrera_<sensor>_L1_<YYYY-MM>.nc
    osm/          mpa_nominatim.geojson
  processed/    harmonised, versioned
    sst_cabrera_daily.zarr
    socib_cabrera_daily.nc
    cabrera_mpa.geojson
  exports/      read by the services, versioned
    meta.json
    parquet/      daily, yearly, events, pixels, validation
    stac/         catalog.json and its collection and items
```

The reasons for this split are in [Architecture](architecture.md#three-data-layers).

## Processed series

### `sst_cabrera_daily.zarr`

| Item | Value |
|---|---|
| Variable | `sea_surface_temperature`, °C, CF `standard_name` `sea_surface_temperature` |
| Dimensions | `time` (daily, from 1982-01-01), `latitude` (10), `longitude` (14) |
| Chunks | 4096 days by the whole grid |
| Format | Zarr version 3, no consolidated metadata |
| Attributes | `source` (products and switch date), `rep_end`, `nrt_bias_correction_degC` (readable), `nrt_monthly_bias` (JSON, read by `update_sst`), `nrt_bias_overlap_days`, `Conventions` |

REP days come first; from the day after `rep_end`, the values are NRT days regridded and corrected (see [Method](method.md#joining-reprocessed-and-near-real-time-sst)).

### `socib_cabrera_daily.nc`

CF NetCDF with `sea_water_temperature` (°C) on dimensions `depth` (1, 13, 16.7 m, positive down) and `time` (daily). Daily means of the QC-filtered measurements; the excluded periods are listed in the `excluded_days` attribute.

### `cabrera_mpa.geojson`

One GeoJSON Feature: the park polygon and the properties `name`, `osm_relation`, `wdpa_id` and `source`. The raw Nominatim answer stays in `data/raw/osm`.

## Exports

### `meta.json`

| Key | Content |
|---|---|
| `generated`, `last_date` | Build time (UTC) and last day of data |
| `mpa` | Name, WDPA id, OSM relation, area (km²), number of pixels inside |
| `station` | Name and position of the SOCIB station |
| `method` | Reference, baseline years, percentile, pooling half-window, smoothing width, minimum duration, largest gap merged |
| `sst_source`, `nrt_bias_correction`, `nrt_bias_overlap_days` | Satellite provenance and the REP/NRT correction |
| `insitu` | QC flags kept and minimum daily coverage |
| `scenarios`, `summer_months` | Precomputed warmings (°C) and the months counted as summer |
| `current_event` | The ongoing heatwave on the last day, or `null` |
| `insitu_excluded` | Periods removed after inspection, with the reason |

### Parquet tables

All in `data/exports/parquet`.

**`daily`**: one row per day of the MPA-mean series (16,337 rows at the September 2026 build).

| Column | Type | Unit | Content |
|---|---|---|---|
| `date` | timestamp | | Day (UTC) |
| `sst` | double | °C | Mean SST of the pixels inside the MPA |
| `climatology` | double | °C | 1991-2020 climatology for that day of the year |
| `threshold` | double | °C | 90th percentile threshold for that day of the year |
| `mhw` | boolean | | Day inside a detected heatwave |
| `area_percent` | double | % | Share of the MPA pixels in heatwave that day |

`sst`, `climatology` and `threshold` are stored unrounded, because `/scenario` runs the detection on them.

**`yearly`**: one row per year and warming (45 years by 5 warmings).

| Column | Type | Unit | Content |
|---|---|---|---|
| `year` | integer | | Calendar year |
| `delta` | double | °C | Warming: 0 for the observed series |
| `mhw_days` | integer | days | Heatwave days in the year |
| `summer_mhw_days` | integer | days | Heatwave days from June to October |
| `area_percent` | double | % | Mean daily share of the MPA in heatwave |
| `n_days` | integer | days | Days with data (below 365 for the current year) |
| `sst_mean` | double | °C | Mean of the observed series |
| `intensity_cumulative` | double | °C·days | Sum of the observed departures from climatology on heatwave days |

`n_days`, `sst_mean` and `intensity_cumulative` describe the observed series and are repeated on the rows of every warming.

**`events`**: one row per observed heatwave on the MPA-mean series.

| Column | Type | Unit | Content |
|---|---|---|---|
| `start`, `end` | text | | First and last day, ISO format |
| `duration` | integer | days | Length |
| `intensity_max` | double | °C | Largest departure from climatology |
| `intensity_mean` | double | °C | Mean departure from climatology |
| `intensity_cumulative` | double | °C·days | Sum of the departures |
| `category` | text | | Moderate, Strong, Severe or Extreme |

**`pixels`**: one row per year, warming and pixel with data (45 × 5 × 140).

| Column | Type | Unit | Content |
|---|---|---|---|
| `year`, `delta` | integer, double | , °C | Year and warming |
| `latitude`, `longitude` | double | degrees | Pixel centre |
| `in_mpa` | boolean | | Centre inside the park |
| `mhw_days` | integer | days | Heatwave days, detected on that pixel against its own climatology |

**`validation`**: one row per day and sensor depth from the first in-situ day.

| Column | Type | Unit | Content |
|---|---|---|---|
| `date` | timestamp | | Day (UTC) |
| `depth_m` | double | m | Sensor depth |
| `station_sst` | double | °C | Daily mean of the sensor, empty when missing or excluded |
| `satellite_sst` | double | °C | Satellite SST of the pixel containing the station |

### STAC catalog

`data/exports/stac` holds a static, self-contained STAC 1.1 catalog: one collection and three items (satellite SST, SOCIB station, heatwave indicators). Items carry the spatial and temporal extent, the providers, their licence and links to the files (Zarr store, NetCDF file, `meta.json`, Parquet tables). The catalog is validated against the STAC schemas by the test suite.

## Reproducibility

`make build` is deterministic: rebuilding from the committed processed series gives byte-identical Parquet and STAC files, on macOS (ARM) as on Linux (x86), only the `generated` time of `meta.json` changes. The CI rebuilds the exports on every push and fails if they differ from the commit.

## Licences and attribution

!!! info "Code and data are licensed separately"

    The **code** is under the MIT licence. The **data** in `data/` derive from third-party sources and stay under their terms.

| Source | Licence | Required attribution |
|---|---|---|
| Copernicus Marine SST | [Copernicus Marine Service licence](https://marine.copernicus.eu/user-corner/service-commitments-and-licence): free use, adaptation and redistribution with attribution | "Generated using E.U. Copernicus Marine Service Information", with the DOIs [10.48670/moi-00173](https://doi.org/10.48670/moi-00173) and [10.48670/moi-00172](https://doi.org/10.48670/moi-00172) |
| SOCIB Station Cabrera | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), see the [SOCIB data terms of use](https://www.socib.es/en/what-we-do/metocean-data/data-terms-of-use) | SOCIB, Balearic Islands Coastal Observing and Forecasting System |
| MPA boundary | [ODbL](https://opendatacommons.org/licenses/odbl/) | © OpenStreetMap contributors. The boundary file, a derived database, stays under ODbL |
| Dashboard basemap | Esri terms of use | Esri, GEBCO, NOAA (displayed on the maps) |

The exported indicators combine Copernicus and SOCIB data within the OpenStreetMap boundary, so they carry the three attributions. The STAC catalog records the same licences per item.
