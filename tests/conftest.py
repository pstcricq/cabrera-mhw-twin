import numpy as np
import pandas as pd
import pytest
import xarray as xr


@pytest.fixture
def sst_cube():
    """Small SST cube: 4 x 5 pixels over three years, with a seasonal cycle."""
    time = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    lat = np.array([38.95, 39.0, 39.05, 39.1])
    lon = np.array([2.9, 2.95, 3.0, 3.05, 3.1])
    doy = time.dayofyear.to_numpy()[:, None, None]
    warmer = np.linspace(0, 0.5, lat.size)[None, :, None]
    values = 20 + 5 * np.sin(2 * np.pi * (doy - 120) / 365) + warmer + 0 * lon
    return xr.Dataset(
        {"sea_surface_temperature": (("time", "latitude", "longitude"), values)},
        coords={"time": time, "latitude": lat, "longitude": lon},
    )


@pytest.fixture
def socib_file(tmp_path):
    """A month of SOCIB-style mooring data: 10 minute steps, QC flags, one short day."""
    time = pd.date_range("2025-08-01", "2025-08-31 23:50", freq="10min")
    temp = 25 + np.sin(np.arange(time.size) / 144 * 2 * np.pi)
    qc = np.ones(time.size)
    qc[(time.day == 5)] = 4  # a whole day flagged bad
    keep = ~((time.day == 10) & (time.hour >= 3))  # 10 August: only three hours
    ds = xr.Dataset(
        {
            "WTR_TEM": ("time", temp[keep]),
            "QC_WTR_TEM": ("time", qc[keep]),
            "DEPTH": ((), -13.0),
        },
        coords={"time": time[keep]},
    )
    path = tmp_path / "dep0001_station-cabrera_scb-sbe37004_L1_2025-08.nc"
    ds.to_netcdf(path)
    return path
