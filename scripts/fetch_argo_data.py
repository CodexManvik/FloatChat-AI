"""
Download real ARGO float profiles from the Ifremer ERDDAP server and save them
as a compact seed file (data/argo_profiles.csv.gz) used by ingest.py.

Profiles are thinned to a fixed set of standard pressure levels so the seed
stays small while keeping the shape of every profile.

Usage:
    python scripts/fetch_argo_data.py --start 2024-01-01 --end 2024-04-01
"""

import argparse
import io
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ERDDAP = "https://erddap.ifremer.fr/erddap/tabledap"
CORE = ("ArgoFloats", "platform_number,cycle_number,time,latitude,longitude,pres,temp,psal", "&temp!=NaN&psal!=NaN")
BGC = ("ArgoFloats-synthetic-BGC", "platform_number,cycle_number,time,latitude,longitude,pres,doxy_adjusted",
       "&doxy_adjusted!=NaN")
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "argo_profiles.csv.gz"

# Standard levels (dbar) each profile is interpolated onto
STANDARD_LEVELS = np.array(
    [5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
     600, 700, 800, 900, 1000, 1200, 1400, 1600, 1800, 2000], dtype=float
)


def fetch_window(dataset, start, end, bbox, retries=3):
    name, variables, extra = dataset
    lat_min, lat_max, lon_min, lon_max = bbox
    query = (
        f"{variables}"
        f"&time>={start:%Y-%m-%dT%H:%M:%SZ}&time<{end:%Y-%m-%dT%H:%M:%SZ}"
        f"&latitude>={lat_min}&latitude<={lat_max}"
        f"&longitude>={lon_min}&longitude<={lon_max}"
        f"&pres<=2050{extra}"
    )
    url = f"{ERDDAP}/{name}.csv?{urllib.parse.quote(query, safe='&=,')}"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=300)
            if resp.status_code == 404:  # ERDDAP answers 404 when no rows match
                return pd.DataFrame()
            resp.raise_for_status()
            return pd.read_csv(io.StringIO(resp.text), skiprows=[1])
        except Exception as e:
            print(f"   attempt {attempt} failed: {e}")
            time.sleep(5 * attempt)
    return pd.DataFrame()


def thin_profile(group, columns):
    group = group.sort_values("pres").drop_duplicates("pres")
    pres = group["pres"].to_numpy()
    levels = STANDARD_LEVELS[(STANDARD_LEVELS >= pres.min()) & (STANDARD_LEVELS <= pres.max())]
    if len(levels) < 3:
        return None
    out = {"pres": levels}
    for col in columns:
        vals = group[col].to_numpy(dtype=float)
        ok = ~np.isnan(vals)
        out[col] = np.interp(levels, pres[ok], vals[ok]) if ok.sum() >= 2 else np.full(len(levels), np.nan)
    first = group.iloc[0]
    df = pd.DataFrame(out)
    for col in ("platform_number", "cycle_number", "time", "latitude", "longitude"):
        df[col] = first[col]
    return df


def download(dataset, columns, start, end, bbox, window_days):
    frames = []
    cursor = start
    while cursor < end:
        nxt = min(cursor + timedelta(days=window_days), end)
        print(f"   {cursor:%Y-%m-%d} -> {nxt:%Y-%m-%d} ...", end=" ", flush=True)
        raw = fetch_window(dataset, cursor, nxt, bbox)
        thinned = []
        if not raw.empty:
            thinned = [p for _, g in raw.groupby(["platform_number", "cycle_number"])
                       if (p := thin_profile(g, columns)) is not None]
        if thinned:
            frames.append(pd.concat(thinned, ignore_index=True))
        print(f"{len(thinned)} profiles")
        cursor = nxt
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-04-01")
    parser.add_argument("--bbox", default="-40,30,30,120", help="lat_min,lat_max,lon_min,lon_max (default: Indian Ocean)")
    parser.add_argument("--window-days", type=int, default=5)
    args = parser.parse_args()

    bbox = [float(v) for v in args.bbox.split(",")]
    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    print("Core profiles (temperature, salinity):")
    core = download(CORE, ["temp", "psal"], start, end, bbox, args.window_days)
    # A few cycles have both an ascending and a descending profile; keep one
    core = core.drop_duplicates(["platform_number", "cycle_number", "pres"])
    if core.empty:
        sys.exit("No data downloaded - check your network connection.")

    print("BGC profiles (dissolved oxygen):")
    bgc = download(BGC, ["doxy_adjusted"], start, end, bbox, args.window_days)
    if bgc.empty:
        core["doxy"] = np.nan
        df = core
    else:
        bgc = bgc.rename(columns={"doxy_adjusted": "doxy"})[["platform_number", "cycle_number", "pres", "doxy"]]
        bgc = bgc.drop_duplicates(["platform_number", "cycle_number", "pres"])
        df = core.merge(bgc, on=["platform_number", "cycle_number", "pres"], how="left")

    df = df.rename(columns={"platform_number": "wmo_id", "pres": "pressure", "temp": "temperature",
                            "psal": "salinity", "doxy": "oxygen", "latitude": "lat", "longitude": "lon"})
    df = df[["wmo_id", "cycle_number", "time", "lat", "lon", "pressure", "temperature", "salinity", "oxygen"]]
    df = df.round({"lat": 4, "lon": 4, "temperature": 3, "salinity": 3, "oxygen": 2})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False, compression="gzip")
    print(f"\nSaved {len(df):,} rows / {df.groupby(['wmo_id', 'cycle_number']).ngroups:,} profiles "
          f"/ {df['wmo_id'].nunique()} floats to {OUTPUT}")


if __name__ == "__main__":
    main()
