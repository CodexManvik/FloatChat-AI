import xarray as xr
from sqlalchemy import create_engine
import config

ds = xr.open_dataset("tempsal.nc")

df = ds[["TEMP","SAL"]].to_dataframe().reset_index()
df = df.rename(columns={'TAXIS': 'time', 'ZAX': 'depth', 'YAXIS': 'lat', 'XAXIS': 'lon', 'TEMP': 'temperature','SAL': 'salinity'})
df_small = df.head(100_000)
engine = create_engine(config.DATABASE_URL)
df_small.to_sql(
    "measurements",
    engine,
    if_exists="append",   # append to table if it exists
    index=False,
    method='multi',       # batch insert for speed
    chunksize=10_000      # insert in 10k row chunks
)
print("completed")