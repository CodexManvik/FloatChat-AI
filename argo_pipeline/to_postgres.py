# to_postgres.py
import os
import pandas as pd
from sqlalchemy import create_engine, Text, DateTime, Float, text
from dotenv import load_dotenv
from nc_to_dataframe import load_argo_profiles

# Load environment variables
load_dotenv()

def write_to_postgres(df: pd.DataFrame):
    """Write DataFrame to PostgreSQL database"""
    
    # Get database URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    print(f"🔗 Connecting to PostgreSQL...")
    
    try:
        # Create engine
        engine = create_engine(DATABASE_URL, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            print("✅ Successfully connected to PostgreSQL")
        
        # Write data with proper SQLAlchemy types
        df.to_sql("argo_profiles", engine, 
                  if_exists="replace", index=False,
                  dtype={
                      "float_id":     Text,           
                      "datetime":     DateTime,       
                      "latitude":     Float,          
                      "longitude":    Float,          
                      "surface_temp": Float,          
                      "surface_sal":  Float,          
                  })
        
        print(f"✅ Written {len(df)} rows to PostgreSQL table 'argo_profiles'")
        
        # Verify data using text() wrapper
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM argo_profiles")).fetchone()
            print(f"✅ Verified: {result[0]} rows in database")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    nc_file = r"D:\MyProjects\flowchat-mvp\backend\INCOIS_ARGO_APPL\dbase\tempsal.nc"
    
    print("📊 Loading profiles from NetCDF...")
    df_profiles = load_argo_profiles(nc_file)
    
    if len(df_profiles) > 0:
        print("💾 Writing to PostgreSQL...")
        success = write_to_postgres(df_profiles)
        if success:
            print("🎉 Data successfully loaded into PostgreSQL!")
    else:
        print("❌ No profiles to write")
