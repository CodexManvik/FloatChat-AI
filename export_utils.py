"""
Export utilities for ARGO data in various scientific formats
"""

import pandas as pd
import xarray as xr
import numpy as np
from io import StringIO, BytesIO
from datetime import datetime
from sqlalchemy import create_engine
import config

engine = create_engine(config.DATABASE_URL)

def export_to_ascii(data_ids: list) -> str:
    """Export ARGO data to ASCII format following oceanographic standards"""
    
    # Fetch data from PostgreSQL
    ids_tuple = tuple(data_ids)
    sql_query = "SELECT * FROM measurements WHERE id IN %s ORDER BY time, depth;"
    df = pd.read_sql_query(sql_query, engine, params=(ids_tuple,))
    
    # Create ASCII output following ARGO format conventions
    output = StringIO()
    
    # Header
    output.write("# ARGO Float Data Export\n")
    output.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    output.write(f"# Number of profiles: {len(data_ids)}\n")
    output.write("# Format: DATE TIME LAT LON DEPTH TEMP SALINITY\n")
    output.write("# Units: YYYY-MM-DD HH:MM:SS degrees degrees meters celsius psu\n")
    output.write("#" + "="*70 + "\n")
    
    # Data rows
    for _, row in df.iterrows():
        temp_str = f"{row['temperature']:8.3f}" if pd.notna(row['temperature']) else "     NaN"
        sal_str = f"{row['salinity']:8.3f}" if pd.notna(row['salinity']) else "     NaN"
        
        output.write(f"{row['time'].strftime('%Y-%m-%d %H:%M:%S')} "
                    f"{row['lat']:8.3f} {row['lon']:8.3f} "
                    f"{row['depth']:8.1f} {temp_str} {sal_str}\n")
    
    return output.getvalue()

def export_to_netcdf(data_ids: list) -> bytes:
    """Export ARGO data to NetCDF format"""
    
    # Fetch data from PostgreSQL
    ids_tuple = tuple(data_ids)
    sql_query = "SELECT * FROM measurements WHERE id IN %s ORDER BY time, depth;"
    df = pd.read_sql_query(sql_query, engine, params=(ids_tuple,))
    
    # Convert to xarray Dataset
    ds = xr.Dataset({
        'temperature': (['obs'], df['temperature'].values),
        'salinity': (['obs'], df['salinity'].values),
        'latitude': (['obs'], df['lat'].values),
        'longitude': (['obs'], df['lon'].values),
        'depth': (['obs'], df['depth'].values),
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
    buffer = BytesIO()
    ds.to_netcdf(buffer, format='NETCDF4')
    return buffer.getvalue()

def export_to_csv(data_ids: list) -> str:
    """Export ARGO data to CSV format"""
    
    ids_tuple = tuple(data_ids)
    sql_query = "SELECT * FROM measurements WHERE id IN %s ORDER BY time, depth;"
    df = pd.read_sql_query(sql_query, engine, params=(ids_tuple,))
    
    # Reorder columns for better readability
    column_order = ['time', 'lat', 'lon', 'depth', 'temperature', 'salinity']
    df = df[column_order]
    
    return df.to_csv(index=False)