import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import Polygon

from cabrera_twin import config
from cabrera_twin.ingest import insitu, mpa, sst


def test_mask_keeps_cells_whose_centre_is_inside(sst_cube):
    square = Polygon([(2.93, 38.97), (3.02, 38.97), (3.02, 39.07), (2.93, 39.07)])
    mask = mpa.mask_for(sst_cube, square)
    assert mask.dims == ("latitude", "longitude")
    inside = [
        (float(lat), float(lon))
        for lat in mask.latitude
        for lon in mask.longitude
        if bool(mask.sel(latitude=lat, longitude=lon))
    ]
    assert inside == [(39.0, 2.95), (39.0, 3.0), (39.05, 2.95), (39.05, 3.0)]


def test_masked_mean_ignores_the_cells_outside(sst_cube):
    square = Polygon([(2.93, 38.97), (3.02, 38.97), (3.02, 39.07), (2.93, 39.07)])
    mask = mpa.mask_for(sst_cube, square)
    field = sst_cube.sea_surface_temperature.isel(time=0)
    assert float(field.where(mask).mean()) == pytest.approx(
        float(field.sel(latitude=[39.0, 39.05], longitude=[2.95, 3.0]).mean())
    )


def test_insitu_keeps_good_flags_and_full_days(monkeypatch, socib_file):
    monkeypatch.setattr(insitu, "download_monthly_files", lambda path: [socib_file])
    frame = insitu.read_instrument("sbe37004", "unused")
    days = frame.index.day
    assert 5 not in days.tolist(), "a day flagged bad must be dropped"
    assert 10 not in days.tolist(), "a day with three hours of data must be dropped"
    assert len(frame) == 29
    assert (frame.depth == 13.0).all()


def test_insitu_applies_the_manual_exclusions(monkeypatch, socib_file):
    monkeypatch.setattr(insitu, "download_monthly_files", lambda path: [socib_file])
    monkeypatch.setattr(
        config, "SOCIB_EXCLUDE", {"sbe37004": [("2025-08-20", None, "test")]}
    )
    frame = insitu.read_instrument("sbe37004", "unused")
    assert frame.index.max() < pd.Timestamp("2025-08-20")


def _nrt_like(cube, offset_by_month):
    """NRT twin of the cube: coarser grid, its own bias, one day beyond the REP end."""
    time = pd.date_range(cube.time.values[0], "2023-01-05", freq="D")
    lat = np.array([38.9375, 39.0, 39.0625, 39.125])
    lon = np.array([2.875, 2.9375, 3.0, 3.0625, 3.125])
    base = (
        cube.sea_surface_temperature.interp(latitude=lat, longitude=lon)
        .reindex(time=time)
        .ffill("time")
    )
    bias = xr.DataArray(
        [offset_by_month[m] for m in time.month], coords={"time": time}, dims="time"
    )
    return (base - bias + 273.15).to_dataset(name="analysed_sst")


def test_rep_nrt_join_removes_the_monthly_bias(monkeypatch, sst_cube, tmp_path):
    # a spatially uniform field, so the coarse NRT grid round trip stays exact
    sst_cube = sst_cube.copy()
    sst_cube["sea_surface_temperature"] = (
        sst_cube.sea_surface_temperature.mean(["latitude", "longitude"])
        .broadcast_like(sst_cube.sea_surface_temperature)
        .transpose("time", "latitude", "longitude")
    )
    offsets = {m: 0.1 * m for m in range(1, 13)}
    rep = (sst_cube.sea_surface_temperature + 273.15).to_dataset(name="analysed_sst")
    nrt = _nrt_like(sst_cube, offsets)
    calls = iter([rep, nrt])
    monkeypatch.setattr(sst, "_subset", lambda *a, **k: next(calls))
    monkeypatch.setattr(sst, "OUT_STORE", tmp_path / "sst.zarr")
    monkeypatch.setattr(sst, "NRT_OVERLAP_DAYS", 3 * 365)

    merged = sst.fetch_sst().sea_surface_temperature.compute()
    # the tail comes from the NRT product, corrected back onto the REP values
    tail = merged.sel(time=slice("2023-01-01", None))
    assert len(tail.time) == 5
    expected = sst_cube.sea_surface_temperature.isel(time=-1)
    assert float(np.abs(tail.isel(time=0) - expected).max()) < 0.01
    assert not bool(merged.isnull().any()), "no grid point may be lost in the join"


def test_update_appends_only_the_new_days(monkeypatch, sst_cube, tmp_path):
    offsets = {m: 0.1 * m for m in range(1, 13)}
    rep = (sst_cube.sea_surface_temperature + 273.15).to_dataset(name="analysed_sst")
    nrt = _nrt_like(sst_cube, offsets)
    calls = iter([rep, nrt])
    monkeypatch.setattr(sst, "_subset", lambda *a, **k: next(calls))
    monkeypatch.setattr(sst, "OUT_STORE", tmp_path / "sst.zarr")
    built = sst.fetch_sst()
    before = built.time.size
    last = pd.Timestamp(built.time.values[-1])

    # a later run sees two more days from the NRT product
    extra = nrt.sel(time=[nrt.time.values[-1]] * 2).copy()
    extra["time"] = [last + pd.Timedelta(days=1), last + pd.Timedelta(days=2)]
    monkeypatch.setattr(sst, "_subset", lambda *a, **k: extra)
    updated = sst.update_sst()

    assert updated.time.size == before + 2
    assert pd.Timestamp(updated.time.values[-1]) == last + pd.Timedelta(days=2)
    assert not bool(updated.sea_surface_temperature.isnull().any())
