"""Study area, data sources and method parameters."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
EXPORT_DIR = ROOT / "data" / "exports"
META_FILE = EXPORT_DIR / "meta.json"
PARQUET_DIR = EXPORT_DIR / "parquet"
STAC_DIR = EXPORT_DIR / "stac"

# Extraction box around the MPA (degrees)
BBOX = {"lat_min": 38.85, "lat_max": 39.35, "lon_min": 2.75, "lon_max": 3.45}

# Cabrera National Park (2019 extension): OSM relation, WDPA id, reported area (km²)
MPA_NAME = "Cabrera Archipelago National Park"
MPA_OSM_RELATION = 10036151
MPA_WDPA_ID = "196045"
MPA_AREA_KM2 = 909
MPA_FILE = PROCESSED_DIR / "cabrera_mpa.geojson"

# Harmonised daily satellite series (Zarr store)
SST_STORE = PROCESSED_DIR / "sst_cabrera_daily.zarr"

# Copernicus Marine SST datasets (Mediterranean, L4, daily)
SST_REP_DATASET = "cmems_SST_MED_SST_L4_REP_OBSERVATIONS_010_021"
SST_NRT_DATASET = "SST_MED_SST_L4_NRT_OBSERVATIONS_010_004_a_V2"
SST_START = "1982-01-01"

# SOCIB Station Cabrera: THREDDS server, position, instrument catalogue paths
SOCIB_THREDDS = "https://thredds.socib.es/thredds"
SOCIB_STATION = {"name": "SOCIB Station Cabrera", "lat": 39.1507, "lon": 2.9310}
_CTD = "mooring/conductivity_and_temperature_recorder"
SOCIB_INSTRUMENTS = {
    "temprec003": "mooring/temperature_recorder/station_cabrera-scb_temprec003",
    "sbe37004": f"{_CTD}/station_cabrera-scb_sbe37004",
    "sbe37002": f"{_CTD}/station_cabrera-scb_sbe37002",
}

# Days excluded after visual inspection, per instrument:
# (first day, last day or None, reason)
SOCIB_EXCLUDE = {
    "temprec003": [
        (
            "2026-09-20",
            None,
            "+2.6 °C jump in one day while the 13 m sensor and the satellite cool; "
            "flagged good by the automatic QC",
        )
    ],
}

# Smallest share of a day's expected measurements for its mean to be kept
MIN_DAY_COVERAGE = 0.5

# Uniform warmings of the precomputed what-if scenarios, °C
SCENARIO_DELTAS = (0.5, 1.0, 1.5, 2.0)

# Months counted as summer (June to October)
SUMMER_MONTHS = (6, 7, 8, 9, 10)

# Marine heatwave definition (Hobday et al., 2016): baseline period, percentile,
# pooling half-window and smoothing width (days), minimum event length and largest
# gap merged (days)
CLIM_START, CLIM_END = "1991-01-01", "2020-12-31"
PCTILE = 90
WINDOW_HALF_WIDTH = 5
SMOOTH_WIDTH = 31
MIN_DURATION = 5
MAX_GAP = 2
