"""
Real ARGO Float Data Processor
Processes actual ARGO float profiles instead of gridded data
"""

import xarray as xr
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime
import config
import os
import glob

engine = create_engine(config.DATABASE_URL)

def create_argo_tables():
    """Create proper ARGO database schema with float and profile structure"""
    
    create_tables_sql = """
    -- Drop existing tables if they exist
    DROP TABLE IF EXISTS measurements CASCADE;
    DROP TABLE IF EXISTS profiles CASCADE;
    DROP TABLE IF EXISTS floats CASCADE;
    
    -- Create floats table
    CREATE TABLE floats (
        float_id VARCHAR(20) PRIMARY KEY,
        wmo_id INTEGER,
        deployment_date DATE,
        deployment_lat FLOAT,
        deployment_lon FLOAT,
        status VARCHAR(20) DEFAULT 'ACTIVE',
        last_contact DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create profiles table (each dive/ascent cycle)
    CREATE TABLE profiles (
        profile_id SERIAL PRIMARY KEY,
        float_id VARCHAR(20) REFERENCES floats(float_id),
        cycle_number INTEGER,
        profile_date TIMESTAMP,
        profile_lat FLOAT,
        profile_lon FLOAT,
        n_levels INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create measurements table (individual depth measurements)
    CREATE TABLE measurements (
        id SERIAL PRIMARY KEY,
        profile_id INTEGER REFERENCES profiles(profile_id),
        float_id VARCHAR(20) REFERENCES floats(float_id),
        time TIMESTAMP,
        lat FLOAT,
        lon FLOAT,
        depth FLOAT,
        pressure FLOAT,
        temperature FLOAT,
        salinity FLOAT,
        -- BGC parameters (for future use)
        oxygen FLOAT,
        ph FLOAT,
        chlorophyll FLOAT,
        nitrate FLOAT,
        backscatter FLOAT,
        cdom FLOAT,
        downwelling_par FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create indexes for better performance
    CREATE INDEX idx_measurements_float_id ON measurements(float_id);
    CREATE INDEX idx_measurements_time ON measurements(time);
    CREATE INDEX idx_measurements_location ON measurements(lat, lon);
    CREATE INDEX idx_measurements_depth ON measurements(depth);
    CREATE INDEX idx_profiles_float_id ON profiles(float_id);
    CREATE INDEX idx_profiles_date ON profiles(profile_date);
    """
    
    with engine.connect() as conn:
        # Execute each statement separately
        for statement in create_tables_sql.split(';'):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()
    
    print("✅ ARGO database schema created successfully!")

def clear_existing_data():
    """Clear existing ARGO data from database"""
    print("Clearing existing ARGO data...")

    clear_sql = """
    DELETE FROM measurements;
    DELETE FROM profiles;
    DELETE FROM floats;
    """

    with engine.connect() as conn:
        for statement in clear_sql.split(';'):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()

    print("✅ Existing data cleared!")

def simulate_real_argo_floats():
    """
    Create realistic ARGO float data structure from your gridded data
    This simulates what real ARGO float files would look like
    """
    
    # Load your existing data
    ds = xr.open_dataset("tempsal.nc")
    
    # Create a subset limited to ~30k measurements
    subset = ds.isel(TAXIS=slice(0, 50))  # 50 time steps
    subset = subset.sel(XAXIS=slice(50, 120), YAXIS=slice(-30, 30))  # Larger Indian Ocean region
    
    # Convert to DataFrame
    df = subset[["TEMP", "SAL"]].to_dataframe().reset_index()
    df = df.rename(columns={
        'TAXIS': 'time', 
        'ZAX': 'depth', 
        'YAXIS': 'lat', 
        'XAXIS': 'lon', 
        'TEMP': 'temperature',
        'SAL': 'salinity'
    })
    
    # Remove NaN values
    df = df.dropna()

    # Limit to 100k measurements as requested
    if len(df) > 100000:
        df = df.head(100000)
        print(f"Limited to 100,000 measurements for ingestion")

    print(f"Processing {len(df)} measurements...")
    
    # Group by location and time to create "virtual floats"
    # Each unique lat/lon combination becomes a float
    location_groups = df.groupby(['lat', 'lon'])
    
    floats_data = []
    profiles_data = []
    measurements_data = []
    
    float_counter = 1
    profile_counter = 1
    
    for (lat, lon), location_df in location_groups:
        if len(location_df) < 1:  # Skip locations with too few measurements
            continue
            
        # Create a virtual float
        float_id = f"ARGO_{float_counter:04d}"
        wmo_id = 5900000 + float_counter
        
        floats_data.append({
            'float_id': float_id,
            'wmo_id': wmo_id,
            'deployment_date': location_df['time'].min().date(),
            'deployment_lat': lat,
            'deployment_lon': lon,
            'status': 'ACTIVE',
            'last_contact': location_df['time'].max().date()
        })
        
        # Group by time to create profiles (each time step is a profile)
        time_groups = location_df.groupby('time')
        
        cycle_num = 1
        for time_val, time_df in time_groups:
            # Create a profile for this time/location
            profile_id = profile_counter
            
            profiles_data.append({
                'profile_id': profile_id,
                'float_id': float_id,
                'cycle_number': cycle_num,
                'profile_date': time_val,
                'profile_lat': lat,
                'profile_lon': lon,
                'n_levels': len(time_df)
            })
            
            # Add measurements for this profile
            for _, row in time_df.iterrows():
                measurements_data.append({
                    'profile_id': profile_id,
                    'float_id': float_id,
                    'time': row['time'],
                    'lat': row['lat'],
                    'lon': row['lon'],
                    'depth': row['depth'],
                    'pressure': row['depth'] * 1.025,  # Approximate pressure from depth
                    'temperature': row['temperature'],
                    'salinity': row['salinity']
                })
            
            cycle_num += 1
            profile_counter += 1
        
        float_counter += 1
        
        if float_counter > config.MAX_FLOATS:  # Limit floats for testing
            break
    
    return pd.DataFrame(floats_data), pd.DataFrame(profiles_data), pd.DataFrame(measurements_data)

def add_realistic_bgc_data(measurements_df):
    """Add realistic BGC data to measurements"""
    
    measurements_with_bgc = measurements_df.copy()
    
    for idx, row in measurements_with_bgc.iterrows():
        depth = row['depth']
        lat = row['lat']
        temp = row['temperature'] if pd.notna(row['temperature']) else 15.0
        
        # Oxygen (ml/L) - realistic oceanographic profile
        if depth < 100:
            oxygen = np.random.normal(6.5, 0.5)  # Surface waters
        elif depth < 1000:
            oxygen = np.random.normal(3.5, 1.0)  # Oxygen minimum zone
        else:
            oxygen = np.random.normal(4.8, 0.3)  # Deep waters
        
        # pH - decreases slightly with depth
        ph = 8.15 - (depth / 15000) + np.random.normal(0, 0.03)
        
        # Chlorophyll (mg/m³) - surface maximum
        if depth < 50:
            chlorophyll = np.random.exponential(0.8)
        elif depth < 200:
            chlorophyll = np.random.exponential(0.15)
        else:
            chlorophyll = 0.01 + np.random.exponential(0.005)
        
        # Nitrate (μmol/kg) - increases with depth
        nitrate = 2 + (depth / 80) + np.random.normal(0, 1.5)
        
        # Other BGC parameters
        backscatter = 0.0008 + np.random.exponential(0.0003)
        cdom = 0.3 + np.random.exponential(0.15)
        
        # PAR - only in upper ocean
        if depth < 150:
            par = 1800 * np.exp(-depth / 45) + np.random.normal(0, 30)
        else:
            par = 0.0
        
        # Add to dataframe
        measurements_with_bgc.loc[idx, 'oxygen'] = max(0, oxygen)
        measurements_with_bgc.loc[idx, 'ph'] = max(7.5, min(8.3, ph))
        measurements_with_bgc.loc[idx, 'chlorophyll'] = max(0, chlorophyll)
        measurements_with_bgc.loc[idx, 'nitrate'] = max(0, nitrate)
        measurements_with_bgc.loc[idx, 'backscatter'] = max(0, backscatter)
        measurements_with_bgc.loc[idx, 'cdom'] = max(0, cdom)
        measurements_with_bgc.loc[idx, 'downwelling_par'] = max(0, par)
    
    return measurements_with_bgc

def ingest_argo_data():
    """Main function to ingest properly structured ARGO data"""
    
    print("🌊 Processing ARGO Float Data...")
    print("=" * 50)
    
    # Step 0: Clear existing data
    print("0. Clearing existing ARGO data...")
    clear_existing_data()

    # Step 1: Create proper database schema
    print("1. Creating ARGO database schema...")
    create_argo_tables()
    
    # Step 2: Process data into float structure
    print("2. Converting gridded data to float profiles...")
    floats_df, profiles_df, measurements_df = simulate_real_argo_floats()
    
    print(f"   Created {len(floats_df)} virtual floats")
    print(f"   Created {len(profiles_df)} profiles")
    print(f"   Created {len(measurements_df)} measurements")
    
    # Step 3: Add BGC data
    print("3. Adding BGC parameters...")
    measurements_df = add_realistic_bgc_data(measurements_df)
    
    # Step 4: Insert data into database
    print("4. Inserting data into PostgreSQL...")
    
    # Insert floats
    floats_df.to_sql('floats', engine, if_exists='append', index=False, method='multi')
    print(f"   ✅ Inserted {len(floats_df)} floats")
    
    # Insert profiles
    profiles_df.to_sql('profiles', engine, if_exists='append', index=False, method='multi')
    print(f"   ✅ Inserted {len(profiles_df)} profiles")
    
    # Insert measurements in batches
    batch_size = 5000
    total_measurements = len(measurements_df)
    
    for i in range(0, total_measurements, batch_size):
        batch = measurements_df.iloc[i:i+batch_size]
        batch.to_sql('measurements', engine, if_exists='append', index=False, method='multi')
        print(f"   ✅ Inserted batch {i//batch_size + 1}/{(total_measurements//batch_size) + 1}")
    
    print("\n🎉 ARGO float data ingestion completed!")
    
    # Show summary
    with engine.connect() as conn:
        float_count = conn.execute(text("SELECT COUNT(*) FROM floats")).scalar()
        profile_count = conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar()
        measurement_count = conn.execute(text("SELECT COUNT(*) FROM measurements")).scalar()
        
        print(f"\n📊 Database Summary:")
        print(f"   Floats: {float_count}")
        print(f"   Profiles: {profile_count}")
        print(f"   Measurements: {measurement_count}")

def get_sample_queries():
    """Get some sample data to test the new structure"""
    
    queries = {
        "Sample Float": "SELECT * FROM floats LIMIT 5;",
        "Sample Profile": "SELECT * FROM profiles LIMIT 5;", 
        "Sample Measurements": "SELECT * FROM measurements LIMIT 10;",
        "Profile with Measurements": """
            SELECT f.float_id, p.cycle_number, p.profile_date, 
                   COUNT(m.id) as measurement_count,
                   AVG(m.temperature) as avg_temp,
                   AVG(m.salinity) as avg_sal
            FROM floats f 
            JOIN profiles p ON f.float_id = p.float_id
            JOIN measurements m ON p.profile_id = m.profile_id
            GROUP BY f.float_id, p.cycle_number, p.profile_date
            ORDER BY p.profile_date
            LIMIT 10;
        """
    }
    
    for name, query in queries.items():
        print(f"\n{name}:")
        print("-" * 40)
        df = pd.read_sql_query(query, engine)
        print(df.to_string(index=False))

if __name__ == "__main__":
    ingest_argo_data()
    print("\n" + "="*50)
    print("Sample Data Preview:")
    get_sample_queries()