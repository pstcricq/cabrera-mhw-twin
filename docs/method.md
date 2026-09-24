# Method

## Series analysed

The **MPA-mean series** is the daily mean of the satellite pixels whose centre lies inside the park boundary (42 pixels of 0.05°). The mean is not weighted by pixel area: over half a degree of latitude the area of a pixel varies by less than 1 %.

Detection also runs **on every pixel** of the extraction box, each against its own climatology and threshold. A pixel that is naturally warmer than its neighbours is therefore not in permanent heatwave; what the map shows is where the sea departed most often from its own usual state.

## Marine heatwave detection

The definition follows Hobday et al. (2016), with the categories of Hobday et al. (2018). Parameters live in `config.py` and are recorded in `meta.json` at each build.

### Climatology and threshold

Days are indexed on a 366-day calendar, so that 1 March is always day 61. For each day of the year \(d\), the values of the baseline period (1991-2020) that fall within ±5 days of \(d\) are pooled (about 330 values). Their mean gives the climatology \(\bar{T}(d)\), their 90th percentile the threshold \(T_{90}(d)\). 29 February, with four times fewer samples, takes the mean of its two neighbours. Both curves are then smoothed with a 31-day moving average that wraps around the end of the year, and rounded to 10⁻⁶ °C. Floating-point sums differ in their last bits from one processor to another, enough to flip a day that sits exactly on the threshold; the rounding, far below the 0.01 °C resolution of the data, makes every platform compute the same threshold.

### Events

A day is **above the threshold** when \(T(t) > T_{90}(d(t))\). An **event** is a run of at least 5 consecutive days above the threshold. Two events separated by 2 days or fewer are merged, and the days in between count as heatwave days.

For an event, with the departure \(i(t) = T(t) - \bar{T}(d(t))\):

\[
I_{max} = \max_t i(t), \qquad I_{mean} = \frac{1}{D}\sum_t i(t), \qquad I_{cum} = \sum_t i(t)
\]

where \(D\) is the duration in days. The **category** is the largest departure over the event expressed in multiples of the gap between threshold and climatology:

\[
n = \max_t \frac{T(t) - \bar{T}(d(t))}{T_{90}(d(t)) - \bar{T}(d(t))}, \qquad \text{category} = \min(\max(\lfloor n \rfloor, 1), 4)
\]

1 is Moderate, 2 Strong, 3 Severe and 4 Extreme.

### Why a fixed 1991-2020 baseline

1991-2020 is the current 30-year climate normal. With a fixed baseline, the recent rise in heatwave days includes the background warming itself: it answers "how often does the park now exceed what was extreme in its reference climate", the question that matters for species adapted to that climate. A moving or detrended baseline would separate the warming from the variability; it is listed under [Limits](#limits-and-alternatives).

### Check against the reference implementation

!!! success "Identical to the reference code"

    On the same MPA-mean series, the detection gives the same events as the reference code [ecjoliver/marineHeatWaves](https://github.com/ecjoliver/marineHeatWaves): same start, duration, intensities and category for every event (87 events, 1,522 heatwave days at the September 2026 build). The comparison was run outside the project, since the reference code needs NumPy 1.

## Indicators

| Indicator | Definition |
|---|---|
| Heatwave days per year | Days inside an event, per calendar year |
| Summer heatwave days | The same, counted from June to October: the stratified season, when a warm surface layer persists over the seagrass meadows |
| Share of the MPA in heatwave | Each day, the percentage of the 42 park pixels in heatwave (per-pixel detection); per year, the mean of the daily values |
| Cumulative intensity | Sum of the departures from climatology on heatwave days, per year or per event (°C·days) |
| Current event | The event that includes the last day of data, if any |
| SST trend | Least-squares slope of the yearly mean SST over complete years, per decade |

## Joining reprocessed and near-real-time SST

The reprocessed product (REP) is the consistent long record but stops a few weeks before today; the near-real-time product (NRT) reaches yesterday but is produced by a different chain, on a coarser grid (0.0625°). The series is REP up to its last day, then NRT.

1. NRT is downloaded from three years before the end of REP, over the box widened by 0.2°, so its coarser grid surrounds every REP point.
2. NRT land cells are filled from up to two neighbouring cells along each axis, then NRT is linearly interpolated onto the REP grid.
3. Over the three years of overlap, the mean difference REP minus NRT is computed for each calendar month, over the whole grid.
4. Each NRT day receives the correction of its month and is appended after the last REP day.

The correction varies with the season (build of September 2026, °C):

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -0.11 | +0.07 | +0.12 | +0.21 | +0.51 | +0.30 | +0.28 | +0.19 | +0.08 | -0.03 | -0.10 | -0.10 |

A single offset would have been about +0.12 °C: too warm in winter and 0.4 °C too cold in May, right at the start of the heatwave season. The monthly values are stored in the Zarr attributes, and `make update` applies them to the new days without downloading the overlap again. `make data` recomputes them from scratch.

## What-if scenarios

A scenario adds a uniform warming \(\Delta\) to every day of the observed series and runs the detection again against the **unchanged** 1991-2020 climatology and threshold. It answers: how often would the observed variability cross the threshold of the reference climate in a sea \(\Delta\) warmer?

!!! warning "A sensitivity test, not a projection"

    A scenario keeps the observed day-to-day and year-to-year variability, while a warmer climate may also change the variability, the stratification and the seasonality.

The build precomputes \(\Delta\) = 0.5, 1, 1.5 and 2 °C, on the MPA-mean series and on every pixel. The `/scenario` route recomputes the MPA-mean detection for any \(\Delta\) and any window; a test checks that it reproduces the precomputed counts. Over 1991-2020, heatwave days go from 20.0 per year observed to 144.0 at +1 °C. The response is not linear and saturates as almost every day ends above the threshold.

## Validation against the SOCIB station

The satellite value is taken at the pixel nearest to the station (39.1507° N, 2.9310° E) and compared with the daily mean of each sensor, on the days both exist.

### In-situ quality control

1. Only measurements with the SOCIB QC flags 1 (good) and 2 (probably good) are kept.
2. A daily mean is kept when at least 50 % of the expected measurements of that day exist, the expected number coming from the median sampling interval of the file. Partial days (deployment, recovery, the current day) would otherwise let the daily cycle bias the mean.
3. Periods found wrong on inspection are removed, with their reason, in `config.SOCIB_EXCLUDE`. The 1 m sensor is excluded from 20 September 2026: it jumped by 2.6 °C in one day while the 13 m sensor and the satellite cooled, and the automatic QC flagged it good.

Days are UTC, like the satellite product.

### Statistics

Computed in SQL by the `/validation` route, per sensor depth:

\[
\text{bias} = \overline{T_{station} - T_{sat}}, \qquad \text{RMSE} = \sqrt{\overline{(T_{station} - T_{sat})^2}}, \qquad r = \text{Pearson correlation of } T_{station} \text{ and } T_{sat}
\]

The satellite product is a **foundation SST**: the temperature just below the surface, free of the afternoon warming of the skin. At 13 m the agreement is close (r = 0.98, bias -0.18 °C over 205 days). At 16.7 m, where the record covers the summer, the sensor reads almost 2 °C below the satellite (bias -1.84 °C) and the correlation vanishes: the water column is stratified and the surface product no longer describes it. The comparison therefore validates the surface product, and shows how deep it remains representative.

## Limits and alternatives

| Choice made | Limit | Alternative |
|---|---|---|
| Fixed 1991-2020 baseline | Heatwave days include the background warming | Moving 30-year baseline, or detection on detrended SST |
| Mean of the MPA, then detection | A short event on part of the park can vanish in the mean | Detect per pixel, then aggregate: the share of the MPA in heatwave does it |
| A pixel counts in the MPA when its centre is inside | Boundary pixels are all or nothing | Weight each pixel by the fraction of its area inside the park |
| NRT on the 0.0625° grid (`_a_V2`) | Coarser than REP, interpolated | The 0.01° grid (`_c_V2`), averaged down to 0.05° |
| QC flags 1 and 2 kept | Flag 2 values are less certain | Keep flag 1 only (no effect on the current data, almost all flagged 1) |
| One satellite pixel against one station | A 25 km² pixel against a point | Several stations, or high-resolution SST near the coast |
| Satellite surface temperature | *Posidonia oceanica* meadows grow down to tens of metres, below the summer thermocline | In-situ profiles or an ocean model for the water column |
| Pixels near the island | Their footprint mixes sea and coast | Exclude coastal pixels, or use a coastal product |

## References

- Hobday, A. J., et al. (2016). A hierarchical approach to defining marine heatwaves. *Progress in Oceanography*, 141, 227-238.
- Hobday, A. J., et al. (2018). Categorizing and naming marine heatwaves. *Oceanography*, 31(2), 162-173.
- Oliver, E. C. J. marineHeatWaves, reference Python implementation of the Hobday et al. definition, [github.com/ecjoliver/marineHeatWaves](https://github.com/ecjoliver/marineHeatWaves).
