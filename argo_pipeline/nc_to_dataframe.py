# nc_to_dataframe.py

import netCDF4 as nc
import pandas as pd
import numpy as np

def load_argo_profiles(nc_path: str) -> pd.DataFrame:
    """
    Load ARGO profiles from a gridded NetCDF file.
    Creates virtual profiles by sampling the 4D grid.
    """
    print(f"📂 Loading NetCDF file: {nc_path}")
    ds = nc.Dataset(nc_path)

    lat_coords  = ds.variables["XAXIS"][:]  # (91,) latitude coordinates
    lon_coords  = ds.variables["YAXIS"][:]  # (61,) longitude coordinates  
    time_coords = ds.variables["TAXIS"][:]  # (144,) time coordinates
    temp_grid   = ds.variables["TEMP"][:]   # (144, 24, 61, 91) [time, depth, lon, lat]
    sal_grid    = ds.variables["SAL"][:]    # (144, 24, 61, 91) [time, depth, lon, lat]

    print(f"🔍 Grid dimensions: {temp_grid.shape} [time, depth, lon, lat]")

    # Safe units lookup
    time_var = ds.variables["TAXIS"]
    units = getattr(time_var, "units", "days since 1950-01-01")
    
    # Convert to cftime objects
    from netCDF4 import num2date
    dates = num2date(time_coords, units, only_use_cftime_datetimes=True)

    ds.close()

    records = []
    profile_id = 0
    
    # Sample every 10th grid point to avoid too many profiles
    time_step = 10   # every 10th time step
    lat_step = 10    # every 10th latitude
    lon_step = 10    # every 10th longitude

    for t_idx in range(0, len(time_coords), time_step):
        for lat_idx in range(0, len(lat_coords), lat_step):
            for lon_idx in range(0, len(lon_coords), lon_step):
                
                # Extract surface values (depth index 0)
                surface_temp = temp_grid[t_idx, 0, lon_idx, lat_idx]
                surface_sal = sal_grid[t_idx, 0, lon_idx, lat_idx]
                
                # Skip if masked/missing data
                if np.ma.is_masked(surface_temp) or np.ma.is_masked(surface_sal):
                    continue
                
                # Convert to regular floats
                try:
                    temp_val = float(surface_temp)
                    sal_val = float(surface_sal)
                except (ValueError, TypeError):
                    continue
                
                # Skip if values are unrealistic
                if temp_val < -5 or temp_val > 50 or sal_val < 0 or sal_val > 50:
                    continue

                dt_str = dates[t_idx].strftime("%Y-%m-%d %H:%M:%S")

                records.append({
                    "float_id":     f"grid_profile_{profile_id}",
                    "datetime":     dt_str,
                    "latitude":     float(lat_coords[lat_idx]),
                    "longitude":    float(lon_coords[lon_idx]),
                    "surface_temp": temp_val,
                    "surface_sal":  sal_val,
                })
                profile_id += 1

    df = pd.DataFrame(records)
    print(f"✅ Created {len(df)} virtual profiles from grid")
    return df

if __name__ == "__main__":
    nc_file = r"D:\MyProjects\flowchat-mvp\backend\INCOIS_ARGO_APPL\dbase\tempsal.nc"
    out_csv = r"D:\MyProjects\flowchat-mvp\backend\INCOIS_ARGO_APPL\dbase\tempsal_profiles.csv"

    df_profiles = load_argo_profiles(nc_file)
    df_profiles.to_csv(out_csv, index=False)
    print(f"💾 Saved {len(df_profiles)} profiles to {out_csv}")
