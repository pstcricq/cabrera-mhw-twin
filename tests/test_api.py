import pytest
from fastapi.testclient import TestClient

from cabrera_twin import api
from cabrera_twin.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_root_redirects_to_the_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_meta_carries_the_provenance(client):
    meta = client.get("/meta").json()
    assert meta["method"]["reference"].startswith("Hobday")
    assert meta["mpa"]["wdpa_id"]
    assert "0" in meta["scenarios"]


def test_yearly_can_be_windowed(client):
    rows = client.get("/indicators/yearly", params={"start": 2020, "end": 2022}).json()
    assert [r["year"] for r in rows] == [2020, 2021, 2022]


def test_yearly_can_be_filtered_in_sql(client):
    rows = client.get("/indicators/yearly", params={"min_days": 150}).json()
    assert rows and all(r["mhw_days"] >= 150 for r in rows)


def test_yearly_scenario_column_is_warmer(client):
    observed = {
        r["year"]: r["mhw_days"] for r in client.get("/indicators/yearly").json()
    }
    warmed = client.get("/indicators/yearly", params={"delta": 1}).json()
    assert all(r["mhw_days"] >= observed[r["year"]] for r in warmed)


def test_daily_returns_one_year(client):
    days = client.get("/indicators/daily", params={"year": 2015}).json()
    assert len(days) == 365
    assert set(days[0]) == {
        "date",
        "sst",
        "climatology",
        "threshold",
        "mhw",
        "area_percent",
    }


def test_daily_accepts_a_window(client):
    days = client.get(
        "/indicators/daily", params={"start": "2003-06-01", "end": "2003-06-10"}
    ).json()
    assert len(days) == 10


def test_unknown_year_is_a_404(client):
    assert client.get("/indicators/daily", params={"year": 1800}).status_code == 404


def test_events_can_be_filtered_and_sorted(client):
    long_events = client.get("/events", params={"min_duration": 60}).json()
    assert long_events and all(e["duration"] >= 60 for e in long_events)
    severe = client.get("/events", params={"category": "severe"}).json()
    assert all(e["category"] == "Severe" for e in severe)
    recent = client.get(
        "/events", params={"since": "2020-01-01", "order_by": "duration", "limit": 3}
    ).json()
    assert len(recent) == 3
    assert [e["duration"] for e in recent] == sorted(
        (e["duration"] for e in recent), reverse=True
    )
    assert all(e["start"] >= "2020-01-01" for e in recent)


def test_scenario_warms_the_series(client):
    observed = {
        r["year"]: r["mhw_days"]
        for r in client.get("/scenario", params={"delta": 0}).json()["years"]
    }
    warmer = client.get("/scenario", params={"delta": 1}).json()
    assert "not a climate projection" in warmer["note"].lower()
    assert all(r["mhw_days"] >= observed[r["year"]] for r in warmer["years"])


def test_scenario_is_computed_for_any_warming(client):
    half = client.get("/scenario", params={"delta": 0.8}).json()
    full = client.get("/scenario", params={"delta": 1.2}).json()
    assert half["delta_degC"] == 0.8, "a value the pipeline never precomputed"
    assert half["mhw_days"] <= full["mhw_days"]


def test_scenario_accepts_a_window(client):
    summer = client.get(
        "/scenario",
        params={"delta": 1, "start": "2003-06-01", "end": "2003-09-30"},
    ).json()
    assert summer["window"] == ["2003-06-01", "2003-09-30"]
    assert summer["days_in_window"] == 122
    assert summer["mhw_days"] <= summer["days_in_window"]


def test_grid_matches_the_scenario(client):
    cells = client.get(
        "/grid", params={"year": 2025, "delta": 1, "in_mpa": True}
    ).json()
    assert cells and all(c["in_mpa"] for c in cells)
    observed = client.get("/grid", params={"year": 2025, "in_mpa": True}).json()
    assert sum(c["mhw_days"] for c in cells) >= sum(c["mhw_days"] for c in observed)


def test_grid_without_a_precomputed_scenario_is_a_404(client):
    assert client.get("/grid", params={"year": 2025, "delta": 3}).status_code == 404


def test_boundary_is_geojson(client):
    feature = client.get("/mpa").json()
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Polygon"


def test_validation_stats_per_depth(client):
    rows = {r["depth_m"]: r for r in client.get("/validation").json()}
    assert rows[13.0]["n_days"] > 100
    assert rows[13.0]["r"] > 0.9


def test_validation_daily_can_select_a_depth(client):
    rows = client.get("/validation/daily", params={"depth": 13}).json()
    assert rows and {r["depth_m"] for r in rows} == {13.0}


def test_routes_answer_the_same_in_process(client):
    """The dashboard calls the route functions directly when no API URL is set."""
    over_http = client.get("/indicators/yearly", params={"delta": 1}).json()
    assert api.yearly(delta=1) == over_http
    assert api.events(limit=3) == client.get("/events", params={"limit": 3}).json()


def test_scenario_on_demand_matches_the_precomputed_ones(client):
    """Rounded daily columns once shifted a few near-threshold days."""
    for delta in api.meta()["scenarios"]:
        on_demand = client.get("/scenario", params={"delta": delta}).json()["years"]
        precomputed = client.get("/indicators/yearly", params={"delta": delta}).json()
        assert {r["year"]: r["mhw_days"] for r in on_demand} == {
            r["year"]: r["mhw_days"] for r in precomputed
        }
