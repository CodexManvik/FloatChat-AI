"""One plain-English sentence block per profile; these are what get embedded and searched."""

from collections.abc import Mapping

import pandas as pd


def value_at(levels: pd.DataFrame, depth: float, column: str):
    """Value of `column` at the level closest to `depth` (within 15 %, or 10 m near the surface)."""
    valid = levels[levels[column].notna()]
    if valid.empty:
        return None
    row = valid.loc[(valid["depth"] - depth).abs().idxmin()]
    if abs(row["depth"] - depth) > max(10, depth * 0.15):
        return None
    return float(row[column])


def describe_profile(profile: Mapping, levels: pd.DataFrame) -> str:
    lat, lon = profile["profile_lat"], profile["profile_lon"]
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    parts = [
        f"ARGO float {profile['float_id']} (WMO {profile['float_id']}) profile cycle {profile['cycle_number']} on "
        f"{profile['profile_date']:%d %B %Y} at {abs(lat):.2f}°{ns}, {abs(lon):.2f}°{ew} in the {profile['region']}.",
        f"The profile has {profile['n_levels']} levels from {levels['depth'].min():.0f} m "
        f"to {levels['depth'].max():.0f} m depth.",
    ]
    surface_t, surface_s = value_at(levels, 5, "temperature"), value_at(levels, 5, "salinity")
    if surface_t is not None:
        salinity = f" and surface salinity {surface_s:.2f} PSU." if surface_s is not None else "."
        parts.append(f"Surface temperature was {surface_t:.2f}°C{salinity}")
    for depth in (200, 1000):
        t, s = value_at(levels, depth, "temperature"), value_at(levels, depth, "salinity")
        if t is not None:
            salinity = f" and salinity {s:.2f} PSU." if s is not None else "."
            parts.append(f"At {depth} m the temperature was {t:.2f}°C{salinity}")
    if levels["oxygen"].notna().any():
        low = levels.loc[levels["oxygen"].idxmin()]
        parts.append(f"This BGC float measures dissolved oxygen; the oxygen minimum was "
                     f"{low['oxygen']:.1f} µmol/kg at {low['depth']:.0f} m.")
    if levels["chlorophyll"].notna().any():
        top = levels.loc[levels["chlorophyll"].idxmax()]
        parts.append(f"It also measures chlorophyll; the chlorophyll maximum was "
                     f"{top['chlorophyll']:.2f} mg/m³ at {top['depth']:.0f} m.")
    if levels["nitrate"].notna().any():
        deep = levels[levels["nitrate"].notna()].iloc[-1]
        parts.append(f"Nitrate reached {deep['nitrate']:.1f} µmol/kg at {deep['depth']:.0f} m.")
    if levels["ph"].notna().any():
        shallow = levels[levels["ph"].notna()].iloc[0]
        parts.append(f"The surface pH was {shallow['ph']:.2f}.")
    return " ".join(parts)
