"""Export profiles as CSV, NetCDF or ASCII."""

import os
import tempfile
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

COLUMNS = ["float_id", "profile_id", "time", "lat", "lon", "depth", "pressure",
           "temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]


def fetch_measurements(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(f"""
            SELECT {", ".join(COLUMNS)} FROM measurements
            WHERE id = ANY(:ids) OR profile_id = ANY(:profile_ids)
            ORDER BY float_id, time, depth
        """), conn, params={"ids": list(data_ids or []), "profile_ids": list(profile_ids or [])})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def export_to_csv(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> str:
    return fetch_measurements(engine, data_ids, profile_ids).to_csv(index=False)


def export_to_ascii(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> str:
    df = fetch_measurements(engine, data_ids, profile_ids)
    out = StringIO()
    out.write("# ARGO Float Data Export\n")
    out.write(f"# Generated: {_now()}\n")
    out.write(f"# Number of profiles: {df['profile_id'].nunique()}\n")
    out.write("# Format: FLOAT DATE TIME LAT LON DEPTH TEMP SALINITY OXYGEN\n")
    out.write("# Units: WMO-ID YYYY-MM-DD HH:MM:SS degrees degrees meters celsius psu umol/kg\n")
    out.write("#" + "=" * 70 + "\n")

    def num(value, fmt):
        return format(value, fmt) if pd.notna(value) else "     NaN"

    for _, row in df.iterrows():
        out.write(f"{row['float_id']:>8} {row['time']:%Y-%m-%d %H:%M:%S} {row['lat']:8.3f} {row['lon']:8.3f} "
                  f"{row['depth']:8.1f} {num(row['temperature'], '8.3f')} {num(row['salinity'], '8.3f')} "
                  f"{num(row['oxygen'], '8.2f')}\n")
    return out.getvalue()


def export_to_netcdf(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> bytes:
    import xarray as xr  # imported lazily: keeps the API's resting memory low

    df = fetch_measurements(engine, data_ids, profile_ids)
    variables = {name: (["obs"], df[name].astype(float).to_numpy())
                 for name in ("temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph", "depth")}
    ds = xr.Dataset({
        "float_id": (["obs"], df["float_id"].to_numpy(dtype=str)),
        "latitude": (["obs"], df["lat"].to_numpy()),
        "longitude": (["obs"], df["lon"].to_numpy()),
        "time": (["obs"], pd.to_datetime(df["time"]).to_numpy()),
        **variables,
    })
    ds.attrs = {"title": "ARGO Float Data Export", "institution": "FloatChat",
                "source": "Argo GDAC via Ifremer ERDDAP", "history": f"Created {_now()}", "Conventions": "CF-1.6"}
    units = {"temperature": ("sea_water_temperature", "degree_Celsius"),
             "salinity": ("sea_water_practical_salinity", "psu"),
             "oxygen": ("moles_of_oxygen_per_unit_mass_in_sea_water", "micromole/kg"),
             "chlorophyll": ("mass_concentration_of_chlorophyll_a_in_sea_water", "mg/m3"),
             "nitrate": ("moles_of_nitrate_per_unit_mass_in_sea_water", "micromole/kg"),
             "ph": ("sea_water_ph_reported_on_total_scale", "1"),
             "depth": ("depth", "m")}
    for name, (standard_name, unit) in units.items():
        ds[name].attrs = {"standard_name": standard_name, "units": unit}
    with tempfile.TemporaryDirectory() as tmp:  # netCDF4 can only write to a real file
        path = os.path.join(tmp, "argo_data.nc")
        ds.to_netcdf(path, format="NETCDF4", engine="netcdf4")
        with open(path, "rb") as f:
            return f.read()


EXPORTERS = {
    "csv": (export_to_csv, "text/csv", "argo_data.csv"),
    "netcdf": (export_to_netcdf, "application/x-netcdf", "argo_data.nc"),
    "ascii": (export_to_ascii, "text/plain", "argo_data.txt"),
}
