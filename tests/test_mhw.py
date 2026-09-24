import numpy as np
import pandas as pd
import pytest

from cabrera_twin.analysis import mhw


def seasonal_series(
    start="1991-01-01", end="2020-12-31", amplitude=5, noise=0.3, seed=0
):
    """Synthetic SST: 20 degC mean, seasonal cycle, gaussian noise."""
    index = pd.date_range(start, end, freq="D")
    rng = np.random.default_rng(seed)
    cycle = 20 + amplitude * np.sin(2 * np.pi * (mhw.doy366(index) - 120) / 366)
    return pd.Series(cycle + rng.normal(0, noise, len(index)), index=index)


def test_doy366_aligns_leap_and_common_years():
    days = pd.to_datetime(
        ["2023-02-28", "2023-03-01", "2024-02-29", "2024-03-01", "2023-12-31"]
    )
    assert mhw.doy366(days).tolist() == [59, 61, 60, 61, 366]


def test_climatology_recovers_seasonal_cycle():
    clim = mhw.climatology(seasonal_series())
    truth = 20 + 5 * np.sin(2 * np.pi * (clim.index.to_numpy() - 120) / 366)
    assert np.abs(clim.seas - truth).max() < 0.1
    assert (clim.thresh > clim.seas).all()


def test_threshold_is_the_90th_percentile():
    clim = mhw.climatology(seasonal_series(amplitude=0))
    # 90th percentile of N(0, 0.3) is 0.38 above the mean
    assert (clim.thresh - clim.seas).mean() == pytest.approx(0.38, abs=0.02)


def _daily(sst_values, thresh=1.0):
    index = pd.date_range("2022-06-01", periods=len(sst_values), freq="D")
    return pd.DataFrame({"sst": sst_values, "seas": 0.0, "thresh": thresh}, index=index)


def test_short_exceedance_is_not_an_event():
    daily = _daily([0, 2, 2, 2, 2, 0, 0])
    assert not mhw.event_mask(daily).any()


def test_five_days_make_an_event_and_short_gaps_merge():
    values = [0] + [2] * 5 + [0] * 2 + [2] * 5 + [0] * 3 + [2] * 5 + [0]
    mask, events = mhw.detect(_daily(values))
    # the 2-day gap is merged, the 3-day gap is not
    assert [(e.start.day, e.duration) for e in events] == [(2, 12), (17, 5)]
    assert mask.sum() == 17


def test_category_from_peak_anomaly():
    values = [0] + [1.5, 2.5, 3.2, 2.0, 1.5] + [0]
    _, [event] = mhw.detect(_daily(values))
    assert event.intensity_max == pytest.approx(3.2)
    assert event.as_dict()["category"] == "Severe"


def test_category_uses_normalised_intensity_not_raw_peak():
    daily = _daily([0, 2.0, 2.0, 1.8, 2.0, 2.0, 0])
    # a narrow threshold on the 4th day makes it the most intense
    # relative to its threshold
    daily.loc[daily.index[3], "thresh"] = 0.5
    _, [event] = mhw.detect(daily)
    assert event.as_dict()["category"] == "Severe"
