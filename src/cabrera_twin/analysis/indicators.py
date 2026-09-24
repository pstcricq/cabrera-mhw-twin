"""Heatwave indicators from the processed series: on the MPA mean, per pixel, per
year and per scenario, plus the satellite against the SOCIB station.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import xarray as xr

from cabrera_twin import config
from cabrera_twin.analysis import mhw, whatif
from cabrera_twin.ingest import insitu


def rounded(values, digits=2) -> list:
    return [None if np.isnan(v) else round(float(v), digits) for v in values]


@dataclass
class Indicators:
    clim: pd.DataFrame
    daily: pd.DataFrame
    events: list[mhw.Event]
    yearly: pd.DataFrame
    scenarios: pd.DataFrame
    summer: pd.DataFrame
    grid: dict
    area: dict
    validation: pd.DataFrame
    pixels: int


def mpa_indicators(sst_ds: xr.Dataset, mask: xr.DataArray):
    """Heatwave detection on the MPA-mean SST."""
    series = (
        sst_ds.sea_surface_temperature.where(mask)
        .mean(["latitude", "longitude"])
        .to_series()
    )
    clim = mhw.climatology(series)
    daily = mhw.align(series, clim)
    days, events = mhw.detect(daily)
    daily["mhw"] = days
    return clim, daily, events


def yearly_indicators(daily: pd.DataFrame) -> pd.DataFrame:
    """Heatwave days, observed days, mean SST and cumulative intensity per year."""
    yearly = daily.groupby(daily.index.year).agg(
        mhw_days=("mhw", "sum"), n_days=("sst", "count"), sst_mean=("sst", "mean")
    )
    anomaly = (daily.sst - daily.seas).where(daily.mhw, 0)
    yearly["intensity_cumulative"] = anomaly.groupby(daily.index.year).sum()
    return yearly


def pixel_indicators(sst_ds: xr.Dataset, in_mpa: xr.DataArray) -> tuple[dict, dict]:
    """Heatwave days per pixel and scenario, and the share of the MPA in heatwave.

    Each pixel is compared with its own climatology and threshold, computed once
    and reused for every scenario.
    """
    field = sst_ds.sea_surface_temperature
    years = np.unique(field.time.dt.year.values)
    deltas = (0.0, *config.SCENARIO_DELTAS)
    shape = (len(years), field.latitude.size, field.longitude.size)
    days = {f"{d:g}": np.full(shape, -1, dtype=int) for d in deltas}
    in_heatwave = {f"{d:g}": [] for d in deltas}

    for i in range(field.latitude.size):
        for j in range(field.longitude.size):
            series = field.isel(latitude=i, longitude=j).to_series()
            if series.isna().all():
                continue
            clim = mhw.climatology(series)
            for delta in deltas:
                flags = whatif.scenario_days(series, clim, delta)
                key = f"{delta:g}"
                days[key][:, i, j] = (
                    flags.groupby(flags.index.year).sum().reindex(years).to_numpy()
                )
                if bool(in_mpa.values[i, j]):
                    in_heatwave[key].append(flags.to_numpy())

    dates = field.time.to_index()
    fraction = {
        key: whatif.area_fraction(np.array(masks)) for key, masks in in_heatwave.items()
    }
    grid = {
        "latitude": rounded(field.latitude.values, 4),
        "longitude": rounded(field.longitude.values, 4),
        "in_mpa": in_mpa.values.astype(int).tolist(),
        "mhw_days": {
            key: {str(y): values[k].tolist() for k, y in enumerate(years)}
            for key, values in days.items()
        },
    }
    # daily share for the observed series, yearly mean for every scenario
    area = {
        "fraction": [round(float(v) * 100, 1) for v in fraction["0"]],
        "yearly_mean": {
            key: {
                str(int(y)): round(float(v) * 100, 1)
                for y, v in pd.Series(values, index=dates)
                .groupby(dates.year)
                .mean()
                .items()
            }
            for key, values in fraction.items()
        },
    }
    return grid, area


def validation(sst_ds: xr.Dataset) -> pd.DataFrame:
    """Satellite SST at the station pixel next to the SOCIB daily mean, per depth.

    One row per day and depth since the first in-situ day; the station column is
    empty on days without a valid measurement.
    """
    station = config.SOCIB_STATION
    sat = sst_ds.sea_surface_temperature.sel(
        latitude=station["lat"], longitude=station["lon"], method="nearest"
    ).to_series()
    obs = xr.open_dataset(insitu.OUT_FILE).sea_water_temperature
    dates = pd.date_range(obs.time.values[0], sat.index[-1], freq="D")
    frames = [
        pd.DataFrame(
            {
                "date": dates,
                "depth_m": float(depth),
                "station_sst": obs.sel(depth=depth).to_series().reindex(dates).values,
                "satellite_sst": sat.reindex(dates).values,
            }
        )
        for depth in obs.depth.values
    ]
    return pd.concat(frames, ignore_index=True).round(
        {"station_sst": 3, "satellite_sst": 3}
    )


def compute(sst_ds: xr.Dataset, mask: xr.DataArray) -> Indicators:
    """Every indicator the exports are written from."""
    clim, daily, events = mpa_indicators(sst_ds, mask)
    grid, area = pixel_indicators(sst_ds, mask)
    return Indicators(
        clim=clim,
        daily=daily,
        events=events,
        yearly=yearly_indicators(daily),
        scenarios=whatif.yearly_days(daily.sst, clim),
        summer=whatif.summer_days(daily.sst, clim),
        grid=grid,
        area=area,
        validation=validation(sst_ds),
        pixels=int(mask.sum()),
    )
