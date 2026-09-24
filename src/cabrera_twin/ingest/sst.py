"""Satellite SST from Copernicus Marine (Mediterranean L4, daily).

`fetch_sst` downloads the reprocessed product (REP, from 1982) and the near-real-time
product (NRT) from three years before the end of REP, regrids NRT onto the REP grid,
adds to it the mean REP - NRT difference of its calendar month over the overlap, and
writes REP followed by the corrected NRT days to a Zarr store. `update_sst` appends
the NRT days published since the last run, corrected with the stored monthly values.
Requires `copernicusmarine login` once on the machine.
"""

import json
import shutil
from datetime import date, timedelta

import copernicusmarine
import xarray as xr

from cabrera_twin import config

RAW_DIR = config.RAW_DIR / "copernicus"
REP_FILE = RAW_DIR / "sst_rep.nc"
NRT_FILE = RAW_DIR / "sst_nrt.nc"
OUT_STORE = config.SST_STORE

# Chunks of 4096 days over the whole grid
CHUNKS = {"time": 4096, "latitude": -1, "longitude": -1}
NRT_OVERLAP_DAYS = 3 * 365

# Margin added around the box for NRT, so its coarser grid surrounds every REP point
NRT_PAD_DEGREES = 0.2


def _subset(dataset_id: str, start: str, path, pad: float = 0.0) -> xr.Dataset:
    """Subset from `start` to the last day the dataset holds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    copernicusmarine.subset(
        dataset_id=dataset_id,
        variables=["analysed_sst"],
        minimum_latitude=config.BBOX["lat_min"] - pad,
        maximum_latitude=config.BBOX["lat_max"] + pad,
        minimum_longitude=config.BBOX["lon_min"] - pad,
        maximum_longitude=config.BBOX["lon_max"] + pad,
        start_datetime=start,
        output_directory=path.parent,
        output_filename=path.name,
        overwrite=True,
        disable_progress_bar=True,
    )
    return xr.open_dataset(path)


def open_sst() -> xr.Dataset:
    """The harmonised SST series."""
    return xr.open_zarr(OUT_STORE, consolidated=False)


def _regrid(nrt: xr.Dataset, grid: xr.DataArray) -> xr.DataArray:
    """NRT field in °C, linearly interpolated onto the REP grid.

    Land-masked NRT cells are first filled from up to two neighbouring cells along
    each axis, so sea points next to the coast keep a value after interpolation.
    """
    celsius = nrt.analysed_sst - 273.15
    for dim in ("latitude", "longitude"):
        celsius = celsius.ffill(dim, limit=2).bfill(dim, limit=2)
    return celsius.interp_like(grid, method="linear")


def _write(ds: xr.Dataset) -> xr.Dataset:
    """Replace the store, leaving the old one untouched until the write succeeds."""
    OUT_STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_STORE.with_suffix(".tmp.zarr")
    shutil.rmtree(tmp, ignore_errors=True)
    ds.chunk(CHUNKS).to_zarr(tmp, mode="w", consolidated=False)
    shutil.rmtree(OUT_STORE, ignore_errors=True)
    tmp.rename(OUT_STORE)
    return open_sst()


def fetch_sst() -> xr.Dataset:
    """Daily SST (degC) on the REP grid over the box: REP, then debiased NRT."""
    rep = _subset(config.SST_REP_DATASET, config.SST_START, REP_FILE)
    # drop trailing days whose field is empty
    rep = rep.dropna("time", how="all")
    rep_end = rep.time.values[-1]
    overlap_start = (
        date.fromisoformat(str(rep_end)[:10]) - timedelta(NRT_OVERLAP_DAYS)
    ).isoformat()
    nrt = _subset(config.SST_NRT_DATASET, overlap_start, NRT_FILE, NRT_PAD_DEGREES)

    rep_sst = rep.analysed_sst - 273.15
    nrt_sst = _regrid(nrt, rep_sst.isel(time=0))
    overlap = slice(nrt_sst.time.values[0], rep_end)
    difference = (rep_sst.sel(time=overlap) - nrt_sst.sel(time=overlap)).mean(
        ["latitude", "longitude"]
    )
    bias = difference.groupby("time.month").mean()
    corrected = nrt_sst + bias.sel(month=nrt_sst.time.dt.month).drop_vars("month")
    tail = corrected.sel(
        time=slice(rep_end + (nrt_sst.time[1] - nrt_sst.time[0]).values, None)
    )
    sst = xr.concat([rep_sst, tail], dim="time")

    sst.name = "sea_surface_temperature"
    sst.attrs = {
        "standard_name": "sea_surface_temperature",
        "units": "degree_Celsius",
        "long_name": "Daily L4 foundation SST",
    }
    ds = sst.to_dataset()
    ds.attrs = {
        "title": "Daily satellite SST around Cabrera National Park",
        "source": f"Copernicus Marine Service: {config.SST_REP_DATASET} until "
        f"{str(rep_end)[:10]}, then {config.SST_NRT_DATASET} regridded and debiased",
        "nrt_bias_correction_degC": ", ".join(
            f"{m:02d}: {v:+.3f}"
            for m, v in zip(bias.month.values, bias.values, strict=True)
        ),
        "nrt_bias_overlap_days": NRT_OVERLAP_DAYS,
        # read back by update_sst
        "nrt_monthly_bias": json.dumps(
            {
                int(m): round(float(v), 4)
                for m, v in zip(bias.month.values, bias.values, strict=True)
            }
        ),
        "rep_end": str(rep_end)[:10],
        "Conventions": "CF-1.10",
    }
    return _write(ds)


def update_sst() -> xr.Dataset:
    """Append the NRT days published since the last run, reusing the stored bias."""
    stored = open_sst()
    last = date.fromisoformat(str(stored.time.values[-1])[:10])
    today = date.today()
    if last >= today:
        return stored

    nrt = _subset(
        config.SST_NRT_DATASET,
        (last + timedelta(1)).isoformat(),
        NRT_FILE,
        NRT_PAD_DEGREES,
    )
    grid = stored.sea_surface_temperature.isel(time=0)
    bias = json.loads(stored.attrs["nrt_monthly_bias"])
    new = _regrid(nrt, grid)
    new = new + xr.DataArray(
        [bias[str(m)] for m in new.time.dt.month.values],
        coords={"time": new.time},
        dims="time",
    )
    new = new.sel(time=slice((last + timedelta(1)).isoformat(), None))
    if new.time.size == 0:
        return stored

    new.name = "sea_surface_temperature"
    new.attrs = stored.sea_surface_temperature.attrs
    new.to_dataset().drop_vars("month", errors="ignore").chunk(
        {"time": CHUNKS["time"]}
    ).to_zarr(OUT_STORE, append_dim="time", consolidated=False)
    return open_sst()
