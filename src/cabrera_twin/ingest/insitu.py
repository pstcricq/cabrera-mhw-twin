"""SOCIB Station Cabrera sea water temperature from the SOCIB THREDDS server.

Monthly L1 files are listed from the THREDDS catalog and copied unchanged to
data/raw/socib/: missing files are downloaded, and the latest month of each
instrument again. The local copies are filtered on the SOCIB QC flags (1 good,
2 probably good) and averaged to daily means per instrument depth.
"""

import re
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests
import xarray as xr

from cabrera_twin import config

GOOD_FLAGS = (1, 2)
RAW_DIR = config.RAW_DIR / "socib"
OUT_FILE = config.PROCESSED_DIR / "socib_cabrera_daily.nc"
_NS = {
    "t": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0",
    "xlink": "http://www.w3.org/1999/xlink",
}


def _catalog(path: str) -> ET.Element:
    r = requests.get(f"{config.SOCIB_THREDDS}/catalog/{path}/catalog.xml", timeout=60)
    r.raise_for_status()
    return ET.fromstring(r.content)


def list_monthly_files(instrument_path: str) -> list[str]:
    """Catalog url paths of the monthly L1 files of one instrument, all years."""
    root = _catalog(f"{instrument_path}/L1")
    years = [
        ref.get(f"{{{_NS['xlink']}}}href").split("/")[0]
        for ref in root.iterfind(".//t:catalogRef", _NS)
    ]
    paths = []
    for year in sorted(years):
        for ds in _catalog(f"{instrument_path}/L1/{year}").iterfind(
            ".//t:dataset", _NS
        ):
            url_path = ds.get("urlPath")
            if url_path and re.search(r"_L1_\d{4}-\d{2}\.nc$", url_path):
                paths.append(url_path)
    return sorted(paths)


def download_monthly_files(instrument_path: str) -> list:
    """Local copies of the monthly L1 files of one instrument."""
    url_paths = list_monthly_files(instrument_path)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for url_path in url_paths:
        local = RAW_DIR / url_path.rsplit("/", 1)[1]
        if not local.exists() or url_path == url_paths[-1]:
            r = requests.get(
                f"{config.SOCIB_THREDDS}/fileServer/{url_path}", timeout=120
            )
            r.raise_for_status()
            local.write_bytes(r.content)
        files.append(local)
    return files


def read_instrument(name: str, instrument_path: str) -> pd.DataFrame:
    """Daily mean QC-filtered temperature of one instrument, with its depth."""
    frames = []
    for path in download_monthly_files(instrument_path):
        with xr.open_dataset(path) as ds:
            temp = ds.WTR_TEM.where(ds.QC_WTR_TEM.isin(GOOD_FLAGS))
            daily = temp.resample(time="1D").mean().to_series()
            count = temp.resample(time="1D").count().to_series()
            depth = float(abs(np.ravel(ds.DEPTH.values)[0]))
            step = pd.Series(ds.time.values).diff().median()
        expected = pd.Timedelta("1D") / step
        frames.append(
            pd.DataFrame(
                {"temp": daily, "n_obs": count, "expected": expected, "depth": depth}
            )
        )
    df = pd.concat(frames)
    # keep days with at least MIN_DAY_COVERAGE of their expected measurements
    df = df[df.n_obs >= config.MIN_DAY_COVERAGE * df.expected]
    for start, end, _ in config.SOCIB_EXCLUDE.get(name, []):
        df = df.drop(df.loc[start:end].index)
    df["instrument"] = name
    return df


def fetch_insitu() -> xr.Dataset:
    """Daily temperature at every Station Cabrera depth, saved as CF NetCDF."""
    df = pd.concat(read_instrument(n, p) for n, p in config.SOCIB_INSTRUMENTS.items())
    df = df.reset_index().rename(columns={"index": "time"})
    df["time"] = df["time"].dt.floor("D")
    series = df.groupby(["depth", "time"]).temp.mean()
    ds = series.to_xarray().rename("sea_water_temperature").to_dataset()
    ds["sea_water_temperature"].attrs = {
        "standard_name": "sea_water_temperature",
        "units": "degree_Celsius",
        "long_name": "Daily mean sea water temperature (SOCIB QC flags 1-2)",
    }
    ds["depth"].attrs = {"standard_name": "depth", "units": "m", "positive": "down"}
    ds.attrs = {
        "title": "SOCIB Station Cabrera daily sea water temperature",
        "source": "SOCIB THREDDS, L1 mooring data: "
        + ", ".join(config.SOCIB_INSTRUMENTS),
        "excluded_days": "; ".join(
            f"{n} from {s} to {e or 'end'}: {why}"
            for n, rules in config.SOCIB_EXCLUDE.items()
            for s, e, why in rules
        ),
        "institution": "SOCIB - Balearic Islands Coastal Observing and Forecasting "
        "System",
        "latitude": config.SOCIB_STATION["lat"],
        "longitude": config.SOCIB_STATION["lon"],
        "Conventions": "CF-1.10",
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    # written to a temporary file, then renamed over the output
    tmp = OUT_FILE.with_suffix(".tmp.nc")
    ds.to_netcdf(tmp)
    tmp.replace(OUT_FILE)
    return ds
