import xarray as xr
from sqlalchemy import create_engine

ds = xr.open_dataset("tempsal.nc")
subset = ds.isel(TAXIS=slice(0,5))
subset = subset.sel(XAXIS=slice(30,120), YAXIS=slice(-30,30))
df = subset[["TEMP","SAL"]].to_dataframe().reset_index()
print(df.head())
