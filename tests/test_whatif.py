import numpy as np

from cabrera_twin.analysis import mhw, whatif


def test_warming_can_only_add_heatwave_days(sst_cube):
    series = sst_cube.sea_surface_temperature.isel(latitude=0, longitude=0).to_series()
    clim = mhw.climatology(series, start="2020-01-01", end="2022-12-31")
    counts = [
        int(whatif.scenario_days(series, clim, delta).sum()) for delta in (0, 0.5, 1, 2)
    ]
    assert counts == sorted(counts)
    assert counts[0] < counts[-1]


def test_summer_days_only_count_the_stratified_season(sst_cube):
    series = sst_cube.sea_surface_temperature.isel(latitude=0, longitude=0).to_series()
    clim = mhw.climatology(series, start="2020-01-01", end="2022-12-31")
    full = whatif.yearly_days(series, clim, deltas=(2,))
    summer = whatif.summer_days(series, clim, deltas=(2,))
    assert (summer["2"] <= full["2"]).all()


def test_area_fraction_is_the_share_of_pixels():
    masks = np.array([[True, False, False], [True, True, False]])
    assert whatif.area_fraction(masks).tolist() == [1.0, 0.5, 0.0]
