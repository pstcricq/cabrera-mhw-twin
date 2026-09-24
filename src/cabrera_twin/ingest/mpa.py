"""MPA boundary from OpenStreetMap (Nominatim lookup) and grid masking."""

import json

import numpy as np
import requests
import shapely
import xarray as xr
from shapely.geometry import shape

from cabrera_twin import config

NOMINATIM_LOOKUP = "https://nominatim.openstreetmap.org/lookup"
USER_AGENT = "cabrera-mhw-twin (https://github.com/pstcricq/cabrera-mhw-twin)"
RAW_FILE = config.RAW_DIR / "osm" / "mpa_nominatim.geojson"
MPA_FILE = config.MPA_FILE


def fetch_mpa() -> dict:
    """Download the MPA polygon, keep the raw response, save it as GeoJSON."""
    r = requests.get(
        NOMINATIM_LOOKUP,
        params={
            "osm_ids": f"R{config.MPA_OSM_RELATION}",
            "format": "geojson",
            "polygon_geojson": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    r.raise_for_status()
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.write_bytes(r.content)
    feature = r.json()["features"][0]
    feature["properties"] = {
        "name": config.MPA_NAME,
        "osm_relation": config.MPA_OSM_RELATION,
        "wdpa_id": config.MPA_WDPA_ID,
        "source": "© OpenStreetMap contributors, ODbL",
    }
    MPA_FILE.parent.mkdir(parents=True, exist_ok=True)
    MPA_FILE.write_text(json.dumps(feature, indent=2) + "\n")
    return feature


def load_mpa():
    """MPA polygon as a shapely geometry."""
    return shape(json.loads(MPA_FILE.read_text())["geometry"])


def mask_for(ds: xr.Dataset, geom=None) -> xr.DataArray:
    """Boolean (lat, lon) mask of grid cells whose centre lies inside the MPA."""
    geom = geom if geom is not None else load_mpa()
    lon2d, lat2d = np.meshgrid(ds.longitude.values, ds.latitude.values)
    inside = shapely.contains_xy(geom, lon2d, lat2d)
    return xr.DataArray(
        inside,
        coords={"latitude": ds.latitude, "longitude": ds.longitude},
        dims=("latitude", "longitude"),
    )
