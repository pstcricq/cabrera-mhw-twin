import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import Polygon

from cabrera_twin import config, pipeline
from cabrera_twin.ingest import insitu, mpa, sst


@pytest.fixture
def exports(tmp_path, monkeypatch, sst_cube):
    """Run the whole build on the synthetic cube, in a temporary directory."""
    processed, exports = tmp_path / "processed", tmp_path / "exports"
    processed.mkdir()
    sst_store = processed / "sst.zarr"
    sst_cube.chunk({"time": 512}).to_zarr(sst_store, consolidated=False)

    depths = xr.Dataset(
        {
            "sea_water_temperature": (
                ("depth", "time"),
                np.full((1, len(sst_cube.time)), 21.0),
            )
        },
        coords={"depth": [13.0], "time": sst_cube.time},
    )
    insitu_file = processed / "socib.nc"
    depths.to_netcdf(insitu_file)

    square = Polygon([(2.93, 38.97), (3.02, 38.97), (3.02, 39.07), (2.93, 39.07)])
    boundary = processed / "mpa.geojson"
    boundary.write_text(
        json.dumps(
            {"type": "Feature", "properties": {}, "geometry": square.__geo_interface__}
        )
    )

    monkeypatch.setattr(config, "META_FILE", exports / "meta.json")
    monkeypatch.setattr(config, "PARQUET_DIR", exports / "parquet")
    monkeypatch.setattr(config, "STAC_DIR", exports / "stac")
    monkeypatch.setattr(config, "MPA_FILE", boundary)
    monkeypatch.setattr(config, "CLIM_START", "2020-01-01")
    monkeypatch.setattr(config, "CLIM_END", "2022-12-31")
    monkeypatch.setattr(mpa, "MPA_FILE", boundary)
    monkeypatch.setattr(sst, "OUT_STORE", sst_store)
    monkeypatch.setattr(insitu, "OUT_FILE", insitu_file)
    pipeline.build()
    return exports


def test_build_writes_every_export(exports):
    assert (exports / "meta.json").exists()
    parquet = {p.name for p in (exports / "parquet").glob("*.parquet")}
    assert parquet == {
        "daily.parquet",
        "events.parquet",
        "pixels.parquet",
        "validation.parquet",
        "yearly.parquet",
    }


def test_build_writes_a_valid_stac_catalog(exports):
    import pystac

    catalog = pystac.Catalog.from_file(str(exports / "stac" / "catalog.json"))
    catalog.validate_all()
    items = {item.id for child in catalog.get_children() for item in child.get_items()}
    assert items == {"satellite-sst", "socib-station-cabrera", "heatwave-indicators"}


def _parquet(exports, name: str) -> pd.DataFrame:
    return pd.read_parquet(exports / "parquet" / f"{name}.parquet")


def test_build_indicators_are_consistent(exports):
    meta = json.loads((exports / "meta.json").read_text())
    yearly = _parquet(exports, "yearly")
    pixels = _parquet(exports, "pixels")

    assert meta["mpa"]["pixels"] == 4
    assert sorted(yearly.year.unique()) == [2020, 2021, 2022]
    by_delta = yearly.pivot(index="year", columns="delta", values="mhw_days")
    assert (by_delta[2.0] >= by_delta[0.0]).all()
    assert (yearly.summer_mhw_days <= yearly.mhw_days).all()
    assert {f"{d:g}" for d in pixels.delta.unique()} == set(meta["scenarios"])
    assert yearly.area_percent.between(0, 100).all()


def test_validation_pairs_the_station_with_its_pixel(exports):
    table = _parquet(exports, "validation")
    assert set(table.depth_m) == {13.0}
    both = table.dropna()
    assert len(both) > 300
    assert (both.station_sst == 21.0).all()


def test_daily_table_covers_every_day(exports):
    daily = _parquet(exports, "daily")
    assert daily.date.iloc[-1] == pd.Timestamp("2022-12-31")
    assert daily.date.diff().dropna().eq(pd.Timedelta("1D")).all()
    assert daily.area_percent.between(0, 100).all()
