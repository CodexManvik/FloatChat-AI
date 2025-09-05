# nc_to_sql.py

import netCDF4 as nc
import pandas as pd
import sqlite3
import os
from datetime import datetime

def convert_nc_to_sql(nc_file_path: str, sqlite_db_path: str, table_name: str):
    print(f"📂 Loading NetCDF file: {nc_file_path}")
    try:
        ds = nc.Dataset(nc_file_path)
    except Exception as e:
        print(f"❌ Error opening file: {e}")
        return 0

    vars = list(ds.variables.keys())
    print(f"📋 Variables: {vars}")

    data = {}
    def ext(var):
        if var in ds.variables:
            arr = ds.variables[var][:]
            return arr.flatten() if hasattr(arr, "flatten") else arr
        return None

    # Explicitly fetch time variables
    time_data = ext("TAXIS")
    if time_data is None:
        time_data = ext("time")
    if time_data is None:
        time_data = ext("JULD")
    data["time"] = time_data

    # Other variables
    data["latitude"]    = ext("XAXIS")
    data["longitude"]   = ext("YAXIS")
    data["temperature"] = ext("TEMP")
    data["salinity"]    = ext("SAL")
    data["pressure"]    = ext("ZAX")
    data["depth"]       = data["pressure"]  # use ZAX as depth
    data["float_id"]    = None
    data["cycle_number"]= None

    # Convert numeric time to datetime if needed
    if time_data is not None and time_data.dtype.kind in ("i","f"):
        tv = ds.variables.get("TAXIS") or ds.variables.get("time") or ds.variables.get("JULD")
        if tv and hasattr(tv, "units"):
            from netCDF4 import num2date
            dates = num2date(time_data, tv.units)
            data["time"] = [d.strftime("%Y-%m-%d %H:%M:%S") for d in dates]

    ds.close()

    # Align lengths by padding None
    maxlen = max(len(v) for v in data.values() if v is not None)
    for k, v in data.items():
        if v is None:
            data[k] = [None]*maxlen
        elif len(v) < maxlen:
            data[k] = list(v) + [None]*(maxlen-len(v))

    df = pd.DataFrame(data)
    print(f"✅ DataFrame: {df.shape}, columns: {list(df.columns)}")

    print(f"💾 Saving to SQLite: {sqlite_db_path} → table '{table_name}'")
    conn = sqlite3.connect(sqlite_db_path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"✅ Saved {len(df)} rows")
    return len(df)

if __name__ == "__main__":
    nc_file   = r"D:\MyProjects\flowchat-mvp\backend\INCOIS_ARGO_APPL\dbase\tempsal.nc"
    sqlite_db = r"D:\MyProjects\flowchat-mvp\backend\INCOIS_ARGO_APPL\dbase\tempsal_data.db"
    table     = "tempsal_data"

    if not os.path.exists(nc_file):
        print(f"❌ File not found: {nc_file}")
    else:
        convert_nc_to_sql(nc_file, sqlite_db, table)
