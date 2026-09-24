from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "dashboard" / "streamlit_app.py")


def test_overview_renders_the_headline_numbers():
    app = AppTest.from_file(APP).run(timeout=60)
    assert not app.exception
    labels = [m.label for m in app.metric]
    assert "Record year" in labels
    assert any(label.startswith("Sea surface") for label in labels)


def test_year_explorer_opens_on_the_requested_year():
    app = AppTest.from_file(APP)
    app.switch_page("year_explorer.py")
    app.query_params["year"] = "2003"
    app.run(timeout=60)
    assert not app.exception
    assert app.selectbox[0].value == 2003


def test_trends_answers_any_warming():
    app = AppTest.from_file(APP)
    app.switch_page("trends.py")
    app.query_params["warming"] = "0.8"
    app.run(timeout=60)
    assert not app.exception
    assert app.slider[0].value == 0.8
    assert app.metric[1].label.endswith("+0.8 °C")


def test_validation_has_one_card_per_sensor():
    app = AppTest.from_file(APP)
    app.switch_page("validation.py")
    app.run(timeout=60)
    assert not app.exception
    assert [m.label for m in app.metric] == [
        "Sensor at 1 m",
        "Sensor at 13 m",
        "Sensor at 16.7 m",
    ]


def test_method_page_renders():
    app = AppTest.from_file(APP)
    app.switch_page("method.py")
    app.run(timeout=60)
    assert not app.exception
