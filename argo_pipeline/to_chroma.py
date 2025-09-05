# to_chroma.py
import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import pandas as pd
from nc_to_dataframe import load_argo_profiles

def index_in_chroma(df: pd.DataFrame):
    """
    Index ARGO profiles in Chroma vector database
    """
    print("🔄 Setting up Chroma client...")
    
    # Create Chroma client with persistent storage
    client = chromadb.PersistentClient(path="./chroma_store")
    
    # Create or get collection
    collection_name = "argo_profiles"
    try:
        collection = client.get_collection(collection_name)
        print(f"✅ Using existing collection: {collection_name}")
    except:
        collection = client.create_collection(collection_name)
        print(f"✅ Created new collection: {collection_name}")

    print("🤖 Loading embedding model...")
    # Load embedding model (this will download ~90MB on first run)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    print("📝 Creating text descriptions for profiles...")
    # Create descriptive text for each profile
    texts = []
    for _, row in df.iterrows():
        # Create a natural language description of each profile
        text = (
            f"ARGO float profile {row['float_id']} collected on {row['datetime']} "
            f"at location {row['latitude']:.2f}°N, {row['longitude']:.2f}°E. "
            f"Surface temperature: {row['surface_temp']:.1f}°C, "
            f"Surface salinity: {row['surface_sal']:.1f} PSU. "
            f"Ocean region with coordinates lat={row['latitude']:.2f}, lon={row['longitude']:.2f}."
        )
        texts.append(text)
    
    print("🔮 Generating embeddings...")
    # Generate embeddings
    embeddings = model.encode(texts, show_progress_bar=True)
    
    print("💾 Adding to Chroma collection...")
    # Add to Chroma collection
    collection.add(
        ids=[str(i) for i in range(len(df))],           # Unique IDs
        documents=texts,                                 # Text descriptions
        embeddings=embeddings.tolist(),                  # Vector embeddings
        metadatas=df.to_dict('records')                  # Metadata for each profile
    )
    
    print(f"✅ Indexed {len(df)} profiles in Chroma vector database")
    return collection

def test_chroma_search(collection, model, query: str = "temperature near equator"):
    """
    Test vector search in Chroma
    """
    print(f"\n🔍 Testing search: '{query}'")
    
    # Embed the query
    query_embedding = model.encode([query]).tolist()
    
    # Search in Chroma
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=3
    )
    
    print("📊 Top 3 results:")
    for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        print(f"{i+1}. Float {metadata['float_id']} at {metadata['latitude']:.1f}°N, {metadata['longitude']:.1f}°E")
        print(f"   Temp: {metadata['surface_temp']:.1f}°C, Sal: {metadata['surface_sal']:.1f}")
        print(f"   Date: {metadata['datetime']}")
        print()

if __name__ == "__main__":
    # Load profiles from NetCDF
    nc_file = r"D:\MyProjects\flowchat-mvp\backend\INCOIS_ARGO_APPL\dbase\tempsal.nc"
    
    print("📊 Loading ARGO profiles...")
    df_profiles = load_argo_profiles(nc_file)
    
    if len(df_profiles) > 0:
        print("🚀 Indexing in Chroma...")
        
        # Index in Chroma
        collection = index_in_chroma(df_profiles)
        
        # Load model for testing
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Test searches
        test_chroma_search(collection, model, "high temperature tropical waters")
        test_chroma_search(collection, model, "salinity measurements in Indian Ocean")
        test_chroma_search(collection, model, "recent temperature data")
        
        print("🎉 Chroma indexing complete!")
    else:
        print("❌ No profiles to index")
