"""
Download Argo profiles from the Ifremer ERDDAP server and keep only good data.

Core floats provide temperature and salinity; the synthetic BGC dataset adds
quality-controlled ("adjusted") oxygen, chlorophyll, nitrate and pH.
"""

import io
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

ERDDAP = "https://erddap.ifremer.fr/erddap/tabledap"
BASE_COLUMNS = ("platform_number", "cycle_number", "time", "latitude", "longitude", "pres")
GOOD_QC = (1, 2)  # Argo flags: 1 = good, 2 = probably good


@dataclass(frozen=True)
class Dataset:
    name: str
    variables: tuple[str, ...]
    extra: str = ""


CORE = Dataset("ArgoFloats", ("temp", "psal"), "&pres<=2050")
BGC = Dataset("ArgoFloats-synthetic-BGC",
              ("doxy_adjusted", "chla_adjusted", "nitrate_adjusted", "ph_in_situ_total_adjusted"), "&pres<=2050")


class FetchError(RuntimeError):
    pass


def build_url(dataset: Dataset, start: datetime, end: datetime, bbox) -> str:
    lat_min, lat_max, lon_min, lon_max = bbox
    columns = ",".join(BASE_COLUMNS + dataset.variables + tuple(f"{v}_qc" for v in dataset.variables))
    query = (
        f"{columns}"
        f"&time>={start:%Y-%m-%dT%H:%M:%SZ}&time<{end:%Y-%m-%dT%H:%M:%SZ}"
        f"&latitude>={lat_min}&latitude<={lat_max}&longitude>={lon_min}&longitude<={lon_max}"
        f"{dataset.extra}"
    )
    return f"{ERDDAP}/{dataset.name}.csv?{urllib.parse.quote(query, safe='&=,')}"


def fetch_window(dataset: Dataset, start: datetime, end: datetime, bbox,
                 get=requests.get, sleep=time.sleep, retries: int = 6) -> pd.DataFrame:
    url = build_url(dataset, start, end, bbox)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = get(url, timeout=300)
            if resp.status_code == 404:  # ERDDAP answers 404 when no rows match
                return pd.DataFrame()
            resp.raise_for_status()
            return pd.read_csv(io.StringIO(resp.text), skiprows=[1])
        except Exception as e:
            last_error = e
            if attempt < retries:
                # ERDDAP sometimes refuses connections for a few minutes: back off 10 s, 20 s, ... (about 5 min total)
                sleep(10 * 2 ** (attempt - 1))
    raise FetchError(f"{dataset.name} {start:%Y-%m-%d}..{end:%Y-%m-%d} failed after {retries} attempts: {last_error}")


def apply_qc(df: pd.DataFrame, dataset: Dataset) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    variables = list(dataset.variables)
    for var in variables:
        qc = pd.to_numeric(df[f"{var}_qc"], errors="coerce")
        df.loc[~qc.isin(GOOD_QC), var] = np.nan
    df = df.dropna(subset=variables, how="all")
    df = df.drop_duplicates(["platform_number", "cycle_number", "pres"])
    return df.drop(columns=[f"{v}_qc" for v in variables]).reset_index(drop=True)


def fetch_range(start: datetime, end: datetime, bbox, window_days: int = 5,
                get=requests.get, sleep=time.sleep, log=print) -> tuple[pd.DataFrame, pd.DataFrame]:
    results = {}
    for dataset in (CORE, BGC):
        frames = []
        cursor = start
        while cursor < end:
            nxt = min(cursor + timedelta(days=window_days), end)
            raw = fetch_window(dataset, cursor, nxt, bbox, get=get, sleep=sleep)
            clean = apply_qc(raw, dataset)
            log(f"   {dataset.name} {cursor:%Y-%m-%d} -> {nxt:%Y-%m-%d}: {len(clean):,} rows")
            if not clean.empty:
                frames.append(clean)
            cursor = nxt
        columns = list(BASE_COLUMNS + dataset.variables)
        results[dataset.name] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    return results[CORE.name], results[BGC.name]
