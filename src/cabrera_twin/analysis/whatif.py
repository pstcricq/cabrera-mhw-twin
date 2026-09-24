"""What-if scenarios: the observed series plus a uniform warming, run through the
heatwave detection against the unchanged baseline climatology and threshold.
"""

import numpy as np
import pandas as pd

from cabrera_twin import config
from cabrera_twin.analysis import mhw


def scenario_days(series: pd.Series, clim: pd.DataFrame, delta: float) -> pd.Series:
    """Heatwave day flags for the series warmed by delta degrees."""
    daily = mhw.align(series + delta, clim)
    return pd.Series(mhw.event_mask(daily), index=daily.index)


def yearly_days(
    series: pd.Series, clim: pd.DataFrame, deltas=config.SCENARIO_DELTAS
) -> pd.DataFrame:
    """Heatwave days per year for the observed series and for each warming scenario."""
    columns = {}
    for delta in (0.0, *deltas):
        days = scenario_days(series, clim, delta)
        columns[f"{delta:g}"] = days.groupby(days.index.year).sum()
    return pd.DataFrame(columns)


def summer_days(
    series: pd.Series, clim: pd.DataFrame, deltas=config.SCENARIO_DELTAS
) -> pd.DataFrame:
    """Heatwave days per year counted over config.SUMMER_MONTHS."""
    columns = {}
    for delta in (0.0, *deltas):
        days = scenario_days(series, clim, delta)
        summer = days[days.index.month.isin(config.SUMMER_MONTHS)]
        columns[f"{delta:g}"] = summer.groupby(summer.index.year).sum()
    return pd.DataFrame(columns)


def area_fraction(masks: np.ndarray) -> np.ndarray:
    """Share of the pixels in heatwave each day, from a (pixel, time) boolean array."""
    return masks.mean(axis=0)
