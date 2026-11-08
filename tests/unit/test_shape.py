from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.erddap import BGC, CORE, apply_qc, fetch_window
from pipeline.shape import SEED_COLUMNS, STANDARD_LEVELS, build_tables, to_seed

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BBOX = (-40.0, 30.0, 30.0, 120.0)


class FakeResponse:
    status_code = 200

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def fixture_get(url, timeout):
    name = "erddap_bgc.csv" if "synthetic-BGC" in url else "erddap_core.csv"
    return FakeResponse((FIXTURES / name).read_text())


def load_fixture_frames():
    core = apply_qc(fetch_window(CORE, datetime(2024, 1, 1), datetime(2024, 3, 1), BBOX, get=fixture_get), CORE)
    bgc = apply_qc(fetch_window(BGC, datetime(2024, 1, 1), datetime(2024, 3, 1), BBOX, get=fixture_get), BGC)
    return core, bgc


def seed_for(seed, wmo):
    return seed[seed.wmo_id == wmo].set_index("pressure")


def test_standard_levels():
    assert len(STANDARD_LEVELS) == 24
    assert STANDARD_LEVELS[0] == 5 and STANDARD_LEVELS[-1] == 2000


def test_to_seed_interpolates_onto_standard_levels():
    seed = to_seed(*load_fixture_frames())
    assert list(seed.columns) == SEED_COLUMNS
    arabian = seed_for(seed, 2902203)
    assert list(arabian.index) == [p for p in STANDARD_LEVELS if 5 <= p <= 1000]  # 19 levels
    assert abs(arabian.loc[500.0, "temperature"] - 14.1875) < 0.01  # QC-flagged 500 m value replaced by interpolation
    assert 195 < arabian.loc[5.0, "oxygen"] < 200
    assert arabian.loc[1000.0, "ph"] == 7.8
    assert pd.notna(arabian.loc[20.0, "chlorophyll"])
    assert pd.isna(arabian.loc[100.0, "chlorophyll"])  # no chlorophyll data below 50 m: no extrapolation
    assert arabian["nitrate"].isna().all()
    southern = seed_for(seed, 5905498)
    assert list(southern.index) == [5.0, 10.0, 20.0, 30.0]
    assert southern["oxygen"].isna().all()


def test_to_seed_without_bgc():
    core, _ = load_fixture_frames()
    seed = to_seed(core, pd.DataFrame())
    assert seed["oxygen"].isna().all() and len(seed) == 23


def test_build_tables():
    floats, profiles, measurements = build_tables(to_seed(*load_fixture_frames()))
    assert sorted(floats["float_id"]) == ["2902203", "5905498"]
    assert set(floats["wmo_id"]) == {2902203, 5905498}
    by_float = profiles.set_index("float_id")
    assert by_float.loc["2902203", "region"] == "Arabian Sea"
    assert by_float.loc["5905498", "region"] == "Eastern Indian Ocean"
    assert bool(by_float.loc["2902203", "has_oxygen"]) and bool(by_float.loc["2902203", "has_chlorophyll"])
    assert not bool(by_float.loc["2902203", "has_nitrate"]) and bool(by_float.loc["2902203", "has_ph"])
    assert not bool(by_float.loc["5905498", "has_oxygen"])
    assert by_float.loc["2902203", "n_levels"] == 19
    assert len(measurements) == 23
    assert {"depth", "pressure", "chlorophyll", "nitrate", "ph", "cycle_number"} <= set(measurements.columns)


def test_build_tables_accepts_old_snapshot_without_bgc_columns():
    old = pd.DataFrame({
        "wmo_id": [1901701] * 3, "cycle_number": [10] * 3, "time": ["2024-01-05T10:00:00Z"] * 3,
        "lat": [-34.5] * 3, "lon": [54.9] * 3, "pressure": [5.0, 10.0, 20.0],
        "temperature": [19.8, 19.7, 19.5], "salinity": [35.6] * 3, "oxygen": [None] * 3,
    })
    _, profiles, measurements = build_tables(old)
    assert profiles.iloc[0]["region"] == "Southern Indian Ocean"
    assert measurements["chlorophyll"].isna().all()
