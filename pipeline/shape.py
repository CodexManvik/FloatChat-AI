"""
Turn raw ERDDAP rows into FloatChat tables.

Every profile is interpolated onto 24 standard pressure levels so the dataset
stays small while keeping the shape of each profile. A variable is only
interpolated inside the pressure range where it was actually measured.
"""

import numpy as np
import pandas as pd

from floatchat.regions import region_for
from pipeline.erddap import BGC

STANDARD_LEVELS = np.array(
    [5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
     600, 700, 800, 900, 1000, 1200, 1400, 1600, 1800, 2000], dtype=float
)
KEYS = ["platform_number", "cycle_number"]
CORE_VARS = ["temp", "psal"]
RENAME = {
    "platform_number": "wmo_id", "latitude": "lat", "longitude": "lon", "pres": "pressure",
    "temp": "temperature", "psal": "salinity", "doxy_adjusted": "oxygen", "chla_adjusted": "chlorophyll",
    "nitrate_adjusted": "nitrate", "ph_in_situ_total_adjusted": "ph",
}
SEED_COLUMNS = ["wmo_id", "cycle_number", "time", "lat", "lon", "pressure",
                "temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]
MEASUREMENT_VALUES = ["temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]


def thin_profile(group: pd.DataFrame, columns: list[str], min_levels: int = 3) -> pd.DataFrame | None:
    group = group.sort_values("pres").drop_duplicates("pres")
    pres = group["pres"].to_numpy(dtype=float)
    levels = STANDARD_LEVELS[(STANDARD_LEVELS >= pres.min()) & (STANDARD_LEVELS <= pres.max())]
    if len(levels) < min_levels:
        return None
    out = {"pres": levels}
    has_values = False
    for col in columns:
        values = group[col].to_numpy(dtype=float)
        ok = ~np.isnan(values)
        if ok.sum() >= 2:
            interpolated = np.interp(levels, pres[ok], values[ok])
            measured = (levels >= pres[ok].min()) & (levels <= pres[ok].max())
            out[col] = np.where(measured, interpolated, np.nan)
            has_values = True
        else:
            out[col] = np.full(len(levels), np.nan)
    if not has_values:
        return None
    df = pd.DataFrame(out)
    first = group.iloc[0]
    for col in ("platform_number", "cycle_number", "time", "latitude", "longitude"):
        df[col] = first[col]
    return df


def _thin_all(df: pd.DataFrame, columns: list[str], min_levels: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    thinned = [p for _, g in df.groupby(KEYS) if (p := thin_profile(g, columns, min_levels)) is not None]
    return pd.concat(thinned, ignore_index=True) if thinned else pd.DataFrame()


def to_seed(core: pd.DataFrame, bgc: pd.DataFrame) -> pd.DataFrame:
    seed = _thin_all(core, CORE_VARS, min_levels=3)
    if seed.empty:
        return pd.DataFrame(columns=SEED_COLUMNS)
    bgc_vars = list(BGC.variables)
    bgc_thin = _thin_all(bgc, bgc_vars, min_levels=2)
    if bgc_thin.empty:
        for var in bgc_vars:
            seed[var] = np.nan
    else:
        seed = seed.merge(bgc_thin[KEYS + ["pres"] + bgc_vars], on=KEYS + ["pres"], how="left")
    seed = seed.rename(columns=RENAME)[SEED_COLUMNS]
    return seed.round({"lat": 4, "lon": 4, "temperature": 3, "salinity": 3, "oxygen": 2,
                       "chlorophyll": 4, "nitrate": 2, "ph": 4})


def build_tables(seed: pd.DataFrame):
    seed = seed.reindex(columns=SEED_COLUMNS)  # older snapshots lack the newer BGC columns
    seed = seed.drop_duplicates(["wmo_id", "cycle_number", "pressure"]).copy()
    seed["time"] = pd.to_datetime(seed["time"], utc=True).dt.tz_localize(None)
    seed["float_id"] = seed["wmo_id"].astype("int64").astype(str)
    seed["cycle_number"] = seed["cycle_number"].astype("int64")
    seed["depth"] = seed["pressure"].round(0)  # 1 dbar is ~1 m of seawater (within ~1% to 2,000 m)
    for col in MEASUREMENT_VALUES:
        seed[col] = pd.to_numeric(seed[col], errors="coerce")

    profiles = (
        seed.groupby(["float_id", "cycle_number"], as_index=False)
        .agg(profile_date=("time", "first"), profile_lat=("lat", "first"), profile_lon=("lon", "first"),
             n_levels=("pressure", "size"), oxygen_n=("oxygen", "count"), chlorophyll_n=("chlorophyll", "count"),
             nitrate_n=("nitrate", "count"), ph_n=("ph", "count"))
        .sort_values(["profile_date", "float_id"])
        .reset_index(drop=True)
    )
    for var in ("oxygen", "chlorophyll", "nitrate", "ph"):
        profiles[f"has_{var}"] = profiles.pop(f"{var}_n") > 0
    profiles["region"] = [region_for(lat, lon) for lat, lon in zip(profiles["profile_lat"], profiles["profile_lon"])]

    floats = (
        profiles.sort_values("profile_date")
        .groupby("float_id", as_index=False)
        .agg(deployment_date=("profile_date", "first"), deployment_lat=("profile_lat", "first"),
             deployment_lon=("profile_lon", "first"), last_contact=("profile_date", "last"))
    )
    floats["wmo_id"] = floats["float_id"].astype(int)
    floats["deployment_date"] = floats["deployment_date"].dt.date
    floats["last_contact"] = floats["last_contact"].dt.date

    measurements = seed[["float_id", "cycle_number", "time", "lat", "lon", "depth", "pressure"] + MEASUREMENT_VALUES]
    return floats, profiles, measurements.reset_index(drop=True)
