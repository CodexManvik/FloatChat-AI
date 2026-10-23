"""
Export utilities for ARGO data in various scientific formats
"""

import pandas as pd
import xarray as xr
import numpy as np
import os
import tempfile
from io import StringIO
from datetime import datetime
from sqlalchemy import create_engine, text
import config

engine = create_engine(config.DATABASE_URL)


def fetch_measurements(data_ids: list, profile_ids: list | None = None) -> pd.DataFrame:
    """Measurements selected by measurement id and/or whole profiles"""
    sql_query = text("""
        SELECT * FROM measurements
        WHERE id = ANY(:ids) OR profile_id = ANY(:profile_ids)
        ORDER BY float_id, time, depth
    """)
    with engine.connect() as conn:
        return pd.read_sql_query(sql_query, conn, params={"ids": list(data_ids or []), "profile_ids": list(profile_ids or [])})

def export_to_ascii(data_ids: list, profile_ids: list | None = None) -> str:
    """Export ARGO data to ASCII format following oceanographic standards"""
    
    # Fetch data from PostgreSQL
    df = fetch_measurements(data_ids, profile_ids)
    
    # Create ASCII output following ARGO format conventions
    output = StringIO()
    
    # Header
    output.write("# ARGO Float Data Export\n")
    output.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    output.write(f"# Number of profiles: {df['profile_id'].nunique()}\n")
    output.write("# Format: FLOAT DATE TIME LAT LON DEPTH TEMP SALINITY\n")
    output.write("# Units: WMO-ID YYYY-MM-DD HH:MM:SS degrees degrees meters celsius psu\n")
    output.write("#" + "="*70 + "\n")
    
    # Data rows
    for _, row in df.iterrows():
        temp_str = f"{row['temperature']:8.3f}" if pd.notna(row['temperature']) else "     NaN"
        sal_str = f"{row['salinity']:8.3f}" if pd.notna(row['salinity']) else "     NaN"
        
        output.write(f"{row['float_id']:>8} {row['time'].strftime('%Y-%m-%d %H:%M:%S')} "
                    f"{row['lat']:8.3f} {row['lon']:8.3f} "
                    f"{row['depth']:8.1f} {temp_str} {sal_str}\n")
    
    return output.getvalue()

def export_to_netcdf(data_ids: list, profile_ids: list | None = None) -> bytes:
    """Export ARGO data to NetCDF format"""
    
    # Fetch data from PostgreSQL
    df = fetch_measurements(data_ids, profile_ids)
    
    # Convert to xarray Dataset
    ds = xr.Dataset({
        'float_id': (['obs'], df['float_id'].to_numpy(dtype=str)),
        'temperature': (['obs'], df['temperature'].values),
        'salinity': (['obs'], df['salinity'].values),
        'latitude': (['obs'], df['lat'].values),
        'longitude': (['obs'], df['lon'].values),
        'depth': (['obs'], df['depth'].values),
        'oxygen': (['obs'], df['oxygen'].astype(float).values),
        'time': (['obs'], pd.to_datetime(df['time']).values)
    })
    
    # Add metadata attributes
    ds.attrs = {
        'title': 'ARGO Float Data Export',
        'institution': 'FloatChat System',
        'source': 'ARGO Global Data Assembly Centers',
        'history': f'Created {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}',
        'conventions': 'CF-1.6',
        'format_version': '3.1'
    }
    
    # Variable attributes
    ds['temperature'].attrs = {
        'long_name': 'Sea Water Temperature',
        'standard_name': 'sea_water_temperature',
        'units': 'degree_Celsius',
        'valid_min': -2.0,
        'valid_max': 40.0
    }
    
    ds['salinity'].attrs = {
        'long_name': 'Sea Water Practical Salinity',
        'standard_name': 'sea_water_practical_salinity',
        'units': 'psu',
        'valid_min': 0.0,
        'valid_max': 50.0
    }
    
    # Save to bytes
    # netCDF4 can only write to a real file, so go through a temp file
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'argo_data.nc')
        ds.to_netcdf(path, format='NETCDF4', engine='netcdf4')
        with open(path, 'rb') as f:
            return f.read()

def export_to_csv(data_ids: list, profile_ids: list | None = None) -> str:
    """Export ARGO data to CSV format"""
    
    df = fetch_measurements(data_ids, profile_ids)
    
    # Reorder columns for better readability
    column_order = ['float_id', 'profile_id', 'time', 'lat', 'lon', 'depth', 'pressure', 'temperature', 'salinity', 'oxygen']
    df = df[column_order]
    
    return df.to_csv(index=False)