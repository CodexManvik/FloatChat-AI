# pipeline.py - Complete end-to-end pipeline
import os
from nc_to_dataframe import load_argo_profiles
from to_postgres import write_to_postgres  
from to_chroma import index_in_chroma

def run_full_pipeline():
    """
    Complete ARGO data processing pipeline:
    NetCDF → PostgreSQL + Chroma → Ready for RAG queries
    """
    print("🌊 ARGO Data Processing Pipeline Starting...")
    print("="*50)
    
    # File paths
    nc_file = r"D:\MyProjects\flowchat-mvp\backend\INCOIS_ARGO_APPL\dbase\tempsal.nc"
    
    # Step 1: Load NetCDF data
    print("📊 Step 1: Loading NetCDF data...")
    df_profiles = load_argo_profiles(nc_file)
    
    if len(df_profiles) == 0:
        print("❌ No profiles loaded. Exiting.")
        return False
    
    print(f"✅ Loaded {len(df_profiles)} profiles")
    
    # Step 2: Store in PostgreSQL
    print("\n💾 Step 2: Storing in PostgreSQL...")
    postgres_success = write_to_postgres(df_profiles)
    
    if not postgres_success:
        print("❌ PostgreSQL storage failed. Continuing anyway...")
    
    # Step 3: Index in Chroma
    print("\n🔮 Step 3: Indexing in Chroma...")
    collection = index_in_chroma(df_profiles)
    
    print("\n🎉 Pipeline Complete!")
    print("="*50)
    print("✅ Data available in:")
    print("   - PostgreSQL: Structured queries")
    print("   - Chroma: Vector similarity search")
    print("   - Ready for RAG queries!")
    
    return True

if __name__ == "__main__":
    run_full_pipeline()
