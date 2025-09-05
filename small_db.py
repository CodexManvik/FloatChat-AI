import sqlite3
import pandas as pd
from pathlib import Path

# CONFIG
ORIG_DB = "data/raw/argo/tempsal_data.db"       # Original full database
SMALL_DB = "tempsal_data_small.db"  # Output small prototype DB
ROWS_PER_TABLE = 100000             # Number of rows per table to copy

# Ensure paths are absolute
orig_path = Path(ORIG_DB).resolve()
small_path = Path(SMALL_DB).resolve()

# Connect to the original DB
conn_orig = sqlite3.connect(orig_path)
cursor = conn_orig.cursor()

# List all tables in the DB
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

if not tables:
    print(f"❌ No tables found in {ORIG_DB}")
    conn_orig.close()
    exit(1)

print(f"Tables found: {[t[0] for t in tables]}")

# Create/connect to the small DB
conn_small = sqlite3.connect(small_path)

for table in tables:
    table_name = table[0]
    print(f"Processing table: {table_name}")

    try:
        # Read a sample of rows from the table
        df = pd.read_sql_query(f"SELECT * FROM '{table_name}' LIMIT {ROWS_PER_TABLE}", conn_orig)

        # Write to the small DB
        df.to_sql(table_name, conn_small, if_exists="replace", index=False)
        print(f"✅ Copied {len(df)} rows from {table_name}")
    except Exception as e:
        print(f"❌ Skipped table {table_name} due to error: {e}")

conn_orig.close()
conn_small.close()
print(f"🎉 Small DB created: {SMALL_DB}")
