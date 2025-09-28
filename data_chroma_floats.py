"""
ChromaDB ingestion for proper ARGO float data structure
Creates embeddings that understand float profiles and relationships
"""

from sqlalchemy import create_engine
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
import config

ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url=f"{config.OLLAMA_HOST}/api/embeddings",
    model_name=config.EMBEDDING_MODEL
)

client = chromadb.PersistentClient(path=config.CHROMA_PATH)

# Delete old collection and create new one
try:
    client.delete_collection(name="argo_measurements")
    print("Deleted old collection")
except:
    pass

collection = client.get_or_create_collection(
    name="argo_measurements",
    embedding_function=ollama_ef
)

engine = create_engine(config.DATABASE_URL)

def create_float_aware_embeddings():
    """Create embeddings that understand ARGO float context and profiles"""
    
    # Get comprehensive data with float and profile context
    sql_query = """
    SELECT 
        m.id,
        m.profile_id,
        m.float_id,
        m.time,
        m.lat,
        m.lon,
        m.depth,
        m.temperature,
        m.salinity,
        m.oxygen,
        m.ph,
        m.chlorophyll,
        f.wmo_id,
        f.deployment_date,
        p.cycle_number,
        p.profile_date,
        p.n_levels
    FROM measurements m
    JOIN profiles p ON m.profile_id = p.profile_id
    JOIN floats f ON m.float_id = f.float_id
    ORDER BY m.float_id, p.cycle_number, m.depth;
    """
    
    df_from_postgres = pd.read_sql_query(sql_query, engine)
    print(f"Processing {len(df_from_postgres)} measurements from {df_from_postgres['float_id'].nunique()} floats...")
    
    # Limit documents for testing
    if len(df_from_postgres) > config.MAX_DOCUMENTS:
        df_from_postgres = df_from_postgres.head(config.MAX_DOCUMENTS)
        print(f"Limited to {config.MAX_DOCUMENTS} documents for testing")
    
    batch_size = config.BATCH_SIZE
    total_rows = len(df_from_postgres)
    
    for i in range(0, total_rows, batch_size):
        batch_df = df_from_postgres.iloc[i:i+batch_size]
        documents = []
        metadatas = []
        ids = []
        
        for index, row in batch_df.iterrows():
            # Create rich, contextual descriptions
            temp_str = f"{row['temperature']:.2f}°C" if pd.notna(row['temperature']) else "not available"
            sal_str = f"{row['salinity']:.2f} PSU" if pd.notna(row['salinity']) else "not available"
            
            # Add BGC information
            bgc_info = ""
            if pd.notna(row['oxygen']):
                bgc_info += f" The dissolved oxygen was {row['oxygen']:.2f} ml/L."
            if pd.notna(row['ph']):
                bgc_info += f" The pH was {row['ph']:.2f}."
            if pd.notna(row['chlorophyll']) and row['chlorophyll'] > 0.01:
                bgc_info += f" The chlorophyll concentration was {row['chlorophyll']:.3f} mg/m³."
            
            # Create comprehensive document with float context
            doc = (
                f"ARGO float {row['float_id']} (WMO ID: {row['wmo_id']}) recorded measurements "
                f"on {row['time'].strftime('%Y-%m-%d')} during cycle {row['cycle_number']}. "
                f"The float was located at latitude {row['lat']:.3f}° and longitude {row['lon']:.3f}°. "
                f"At a depth of {row['depth']:.1f} meters, the temperature was {temp_str} "
                f"and the salinity was {sal_str}.{bgc_info} "
                f"This measurement was part of a profile with {row['n_levels']} depth levels. "
                f"The float was deployed on {row['deployment_date']}."
            )
            
            # Rich metadata for retrieval
            meta = {
                'postgres_id': int(row['id']),
                'profile_id': int(row['profile_id']),
                'float_id': str(row['float_id']),
                'wmo_id': int(row['wmo_id']),
                'cycle_number': int(row['cycle_number']),
                'time': row['time'].strftime('%Y-%m-%d'),
                'profile_date': row['profile_date'].strftime('%Y-%m-%d'),
                'depth': float(row['depth']),
                'lat': float(row['lat']),
                'lon': float(row['lon']),
                'n_levels': int(row['n_levels']),
                'has_bgc': bool(pd.notna(row['oxygen']) or pd.notna(row['ph']) or pd.notna(row['chlorophyll']))
            }
            
            documents.append(doc)
            metadatas.append(meta)
            ids.append(str(row['id']))
        
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added batch {i//batch_size + 1}, total documents: {collection.count()}")
    
    print(f"✅ Completed! There are now {collection.count()} documents in the collection")

def create_profile_summaries():
    """Create additional embeddings for profile-level summaries"""
    
    # Get profile summaries
    profile_sql = """
    SELECT 
        p.profile_id,
        p.float_id,
        p.cycle_number,
        p.profile_date,
        p.profile_lat,
        p.profile_lon,
        p.n_levels,
        f.wmo_id,
        AVG(m.temperature) as avg_temp,
        MIN(m.temperature) as min_temp,
        MAX(m.temperature) as max_temp,
        AVG(m.salinity) as avg_sal,
        MIN(m.salinity) as min_sal,
        MAX(m.salinity) as max_sal,
        MIN(m.depth) as min_depth,
        MAX(m.depth) as max_depth,
        AVG(m.oxygen) as avg_oxygen,
        AVG(m.ph) as avg_ph,
        AVG(m.chlorophyll) as avg_chlorophyll
    FROM profiles p
    JOIN floats f ON p.float_id = f.float_id
    JOIN measurements m ON p.profile_id = m.profile_id
    GROUP BY p.profile_id, p.float_id, p.cycle_number, p.profile_date, 
             p.profile_lat, p.profile_lon, p.n_levels, f.wmo_id
    ORDER BY p.profile_date;
    """
    
    profiles_df = pd.read_sql_query(profile_sql, engine)
    print(f"Creating profile summaries for {len(profiles_df)} profiles...")
    
    # Create a separate collection for profile summaries
    try:
        client.delete_collection(name="argo_profiles")
    except:
        pass
    
    profile_collection = client.get_or_create_collection(
        name="argo_profiles",
        embedding_function=ollama_ef
    )
    
    documents = []
    metadatas = []
    ids = []
    
    for _, row in profiles_df.iterrows():
        # Create profile summary document
        temp_range = f"{row['min_temp']:.1f}°C to {row['max_temp']:.1f}°C" if pd.notna(row['min_temp']) else "not available"
        sal_range = f"{row['min_sal']:.2f} to {row['max_sal']:.2f} PSU" if pd.notna(row['min_sal']) else "not available"
        depth_range = f"{row['min_depth']:.0f}m to {row['max_depth']:.0f}m"
        
        bgc_summary = ""
        if pd.notna(row['avg_oxygen']):
            bgc_summary += f" Average oxygen was {row['avg_oxygen']:.2f} ml/L."
        if pd.notna(row['avg_ph']):
            bgc_summary += f" Average pH was {row['avg_ph']:.2f}."
        if pd.notna(row['avg_chlorophyll']):
            bgc_summary += f" Average chlorophyll was {row['avg_chlorophyll']:.3f} mg/m³."
        
        doc = (
            f"ARGO float {row['float_id']} (WMO {row['wmo_id']}) completed profile cycle {row['cycle_number']} "
            f"on {row['profile_date'].strftime('%Y-%m-%d')} at location {row['profile_lat']:.3f}°, {row['profile_lon']:.3f}°. "
            f"This profile contains {row['n_levels']} measurements spanning depths from {depth_range}. "
            f"Temperature ranged from {temp_range} and salinity from {sal_range}.{bgc_summary}"
        )
        
        meta = {
            'profile_id': int(row['profile_id']),
            'float_id': str(row['float_id']),
            'wmo_id': int(row['wmo_id']),
            'cycle_number': int(row['cycle_number']),
            'profile_date': row['profile_date'].strftime('%Y-%m-%d'),
            'lat': float(row['profile_lat']),
            'lon': float(row['profile_lon']),
            'n_levels': int(row['n_levels']),
            'min_depth': float(row['min_depth']),
            'max_depth': float(row['max_depth']),
            'min_temp': float(row['min_temp']) if pd.notna(row['min_temp']) else None,
            'max_temp': float(row['max_temp']) if pd.notna(row['max_temp']) else None,
            'has_bgc': bool(pd.notna(row['avg_oxygen']))
        }
        
        documents.append(doc)
        metadatas.append(meta)
        ids.append(f"profile_{row['profile_id']}")
    
    if documents:
        profile_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"✅ Added {len(documents)} profile summaries")

if __name__ == "__main__":
    print("🌊 Creating ARGO Float-Aware Embeddings")
    print("=" * 50)
    
    create_float_aware_embeddings()
    # create_profile_summaries()  # Skip for now due to metadata format issue
    
    print("\n✅ ChromaDB updated with proper ARGO float structure!")
    print("Now your queries can understand:")
    print("• Individual float trajectories")
    print("• Profile cycles and temporal patterns") 
    print("• Depth relationships within profiles")
    print("• BGC parameter correlations")
    print("• Float deployment and operational context")