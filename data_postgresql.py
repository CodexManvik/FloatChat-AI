import xarray as xr
from sqlalchemy import create_engine
from urllib.parse import quote_plus

ds = xr.open_dataset("tempsal.nc")

df = ds[["TEMP","SAL"]].to_dataframe().reset_index()
df = df.rename(columns={'TAXIS': 'time', 'ZAX': 'depth', 'YAXIS': 'lat', 'XAXIS': 'lon', 'TEMP': 'temperature','SAL': 'salinity'})
df_small = df.head(100_000)
password = quote_plus("Manvik@2005")
engine = create_engine(f"postgresql+psycopg2://postgres:{password}@localhost:5432/argo")
df_small.to_sql(
    "measurements",
    engine,
    if_exists="append",   # append to table if it exists
    index=False,
    method='multi',       # batch insert for speed
    chunksize=10_000      # insert in 10k row chunks
)
print("completed")