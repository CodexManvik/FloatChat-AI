from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from pipeline.erddap import BGC, CORE, FetchError, apply_qc, build_url, fetch_range, fetch_window

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BBOX = (-40.0, 30.0, 30.0, 120.0)
START, END = datetime(2024, 1, 1), datetime(2024, 1, 11)


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code, self.text = status_code, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def fixture_get(url, timeout):
    name = "erddap_bgc.csv" if "synthetic-BGC" in url else "erddap_core.csv"
    return FakeResponse(text=(FIXTURES / name).read_text())


def test_build_url_contains_dataset_columns_and_constraints():
    url = build_url(CORE, START, END, BBOX)
    assert url.startswith("https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.csv?")
    assert "temp_qc" in url and "psal_qc" in url
    assert "time%3E=2024-01-01T00%3A00%3A00Z" in url  # "=" is kept, ">" and ":" are encoded
    assert "latitude%3E=-40.0" in url


def test_fetch_window_parses_csv_and_skips_units_row():
    df = fetch_window(CORE, START, END, BBOX, get=fixture_get, sleep=lambda s: None)
    assert len(df) == 13
    assert df["platform_number"].iloc[0] == 2902203


def test_fetch_window_404_means_no_rows():
    df = fetch_window(CORE, START, END, BBOX, get=lambda url, timeout: FakeResponse(404), sleep=lambda s: None)
    assert df.empty


def test_fetch_window_retries_then_succeeds():
    calls = []

    def flaky(url, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return fixture_get(url, timeout)

    df = fetch_window(CORE, START, END, BBOX, get=flaky, sleep=lambda s: None)
    assert len(calls) == 3 and not df.empty


def test_fetch_window_backs_off_long_enough_for_a_short_outage():
    # ERDDAP refused connections during the first real backfill; retries must outlast a few minutes of that
    calls, waits = [], []

    def refused_five_times(url, timeout):
        calls.append(url)
        if len(calls) <= 5:
            raise ConnectionRefusedError("Connection refused")
        return fixture_get(url, timeout)

    df = fetch_window(CORE, START, END, BBOX, get=refused_five_times, sleep=waits.append)
    assert not df.empty and len(calls) == 6
    assert waits == [10, 20, 40, 80, 160]


def test_fetch_window_raises_after_retries():
    def broken(url, timeout):
        raise ConnectionError("down")

    with pytest.raises(FetchError, match="ArgoFloats"):
        fetch_window(CORE, START, END, BBOX, get=broken, sleep=lambda s: None)


def test_apply_qc_core():
    raw = fetch_window(CORE, START, END, BBOX, get=fixture_get, sleep=lambda s: None)
    clean = apply_qc(raw, CORE)
    assert "temp_qc" not in clean.columns
    row500 = clean[(clean.platform_number == 2902203) & (clean.pres == 500.0)].iloc[0]
    assert pd.isna(row500["temp"]) and row500["psal"] == 35.40      # bad temp QC removed, salinity kept
    assert len(clean[(clean.platform_number == 2902203) & (clean.pres == 1000.0)]) == 1  # duplicate dropped
    assert 40.0 not in clean[clean.platform_number == 5905498]["pres"].tolist()      # all-NaN row dropped


def test_apply_qc_bgc():
    raw = fetch_window(BGC, START, END, BBOX, get=fixture_get, sleep=lambda s: None)
    clean = apply_qc(raw, BGC)
    row200 = clean[clean.pres == 200.0].iloc[0]
    assert pd.isna(row200["chla_adjusted"]) and row200["doxy_adjusted"] == 20.0
    assert clean["nitrate_adjusted"].isna().all()


def test_fetch_range_splits_into_windows():
    urls = []

    def recording_get(url, timeout):
        urls.append(url)
        return fixture_get(url, timeout)

    core, bgc = fetch_range(START, END, BBOX, window_days=5, get=recording_get, sleep=lambda s: None,
                            log=lambda *a, **k: None)
    assert len(urls) == 4  # 2 windows x (core + BGC)
    assert not core.empty and not bgc.empty
