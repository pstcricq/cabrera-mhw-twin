"""Marine heatwave detection following Hobday et al. (2016, 2018).

Climatology and threshold are computed per day of year on a 366-day calendar: values
within +/- WINDOW_HALF_WIDTH days over the baseline period are pooled, then the mean and
the PCTILE percentile are smoothed with a SMOOTH_WIDTH-day circular moving average.
A heatwave is a run of at least MIN_DURATION days above the threshold; runs separated
by at most MAX_GAP days are merged.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cabrera_twin import config

CATEGORIES = {1: "Moderate", 2: "Strong", 3: "Severe", 4: "Extreme"}


def doy366(index: pd.DatetimeIndex) -> np.ndarray:
    """Day of year on a leap-year calendar (1..366): 1 March is always 61."""
    doy = index.dayofyear.to_numpy()
    shift = (~index.is_leap_year) & (index.month > 2)
    return doy + shift


def _circular_smooth(values: np.ndarray, width: int) -> np.ndarray:
    half = width // 2
    padded = np.concatenate([values[-half:], values, values[:half]])
    return np.convolve(padded, np.ones(width) / width, mode="valid")


def climatology(
    sst: pd.Series,
    start=config.CLIM_START,
    end=config.CLIM_END,
    pctile=config.PCTILE,
    half_width=config.WINDOW_HALF_WIDTH,
    smooth=config.SMOOTH_WIDTH,
) -> pd.DataFrame:
    """Seasonal mean and threshold indexed by day of year (1..366)."""
    base = sst.loc[start:end].dropna()
    doys = doy366(base.index)
    values = base.to_numpy()
    seas, thresh = np.empty(366), np.empty(366)
    for d in range(1, 367):
        dist = np.abs(doys - d)
        in_window = np.minimum(dist, 366 - dist) <= half_width
        seas[d - 1] = values[in_window].mean()
        thresh[d - 1] = np.percentile(values[in_window], pctile)
    # 29 February: mean of 28 February and 1 March
    seas[59] = (seas[58] + seas[60]) / 2
    thresh[59] = (thresh[58] + thresh[60]) / 2
    # rounded to 1e-6 °C: the same values on every platform
    return pd.DataFrame(
        {
            "seas": np.round(_circular_smooth(seas, smooth), 6),
            "thresh": np.round(_circular_smooth(thresh, smooth), 6),
        },
        index=pd.Index(range(1, 367), name="doy"),
    )


def align(sst: pd.Series, clim: pd.DataFrame) -> pd.DataFrame:
    """Daily frame with sst, seasonal mean and threshold for each date."""
    doys = doy366(sst.index)
    return pd.DataFrame(
        {
            "sst": sst.to_numpy(),
            "seas": clim.seas.to_numpy()[doys - 1],
            "thresh": clim.thresh.to_numpy()[doys - 1],
        },
        index=sst.index,
    )


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) inclusive index pairs of consecutive True values."""
    edges = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    return list(zip(starts, ends, strict=True))


def event_mask(
    daily: pd.DataFrame, min_duration=config.MIN_DURATION, max_gap=config.MAX_GAP
) -> np.ndarray:
    """Boolean array, True on days belonging to a marine heatwave."""
    above = (daily.sst > daily.thresh).to_numpy()
    runs = [(s, e) for s, e in _runs(above) if e - s + 1 >= min_duration]
    merged: list[list[int]] = []
    for s, e in runs:
        if merged and s - merged[-1][1] - 1 <= max_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    mask = np.zeros(len(daily), dtype=bool)
    for s, e in merged:
        mask[s : e + 1] = True
    return mask


@dataclass
class Event:
    start: pd.Timestamp
    end: pd.Timestamp
    duration: int
    intensity_max: float
    intensity_mean: float
    intensity_cumulative: float
    category: int

    def as_dict(self) -> dict:
        return {
            "start": self.start.date().isoformat(),
            "end": self.end.date().isoformat(),
            "duration": self.duration,
            "intensity_max": round(self.intensity_max, 2),
            "intensity_mean": round(self.intensity_mean, 2),
            "intensity_cumulative": round(self.intensity_cumulative, 1),
            "category": CATEGORIES[self.category],
        }


def detect(daily: pd.DataFrame) -> tuple[np.ndarray, list[Event]]:
    """Heatwave day mask and the list of events with their Hobday metrics."""
    mask = event_mask(daily)
    events = []
    for s, e in _runs(mask):
        chunk = daily.iloc[s : e + 1]
        anomaly = chunk.sst - chunk.seas
        # Category: largest anomaly over the event,
        # in multiples of (threshold - climatology)
        ratio = (anomaly / (chunk.thresh - chunk.seas)).max()
        events.append(
            Event(
                start=chunk.index[0],
                end=chunk.index[-1],
                duration=len(chunk),
                intensity_max=float(anomaly.max()),
                intensity_mean=float(anomaly.mean()),
                intensity_cumulative=float(anomaly.sum()),
                category=int(min(max(np.floor(ratio), 1), 4)),
            )
        )
    return mask, events
