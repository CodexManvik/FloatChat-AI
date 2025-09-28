from sqlalchemy import create_engine
from urllib.parse import quote_plus
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions

ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text"
)

client = chromadb.PersistentClient(path="./chroma_db")
client.delete_collection(name="argo_measurements")
collection = client.get_or_create_collection(name="argo_measurements",embedding_function=ollama_ef)
password = quote_plus("Manvik@2005")
engine = create_engine(f"postgresql+psycopg2://postgres:{password}@localhost:5432/argo")

sql_query = "SELECT * FROM measurements;"
df_from_postgres = pd.read_sql_query(sql_query,engine)

batch_size = 1000
total_rows = len(df_from_postgres)

for i in range(0,total_rows,batch_size):
    batch_df = df_from_postgres.iloc[i:i+batch_size]
    documents = []
    metadatas= []
    ids = []
    for index,row in batch_df.iterrows():
        temp_str = f"{row['temperature']:.2f}°C" if pd.notna(row['temperature']) else "not available"
        sal_str = f"{row['salinity']:.2f} PSU" if pd.notna(row['salinity']) else "not available"
        
        # Add BGC parameters if available
        bgc_info = ""
        if 'oxygen' in row and pd.notna(row['oxygen']):
            bgc_info += f" The dissolved oxygen was {row['oxygen']:.2f} ml/L."
        if 'ph' in row and pd.notna(row['ph']):
            bgc_info += f" The pH was {row['ph']:.2f}."
        if 'chlorophyll' in row and pd.notna(row['chlorophyll']):
            bgc_info += f" The chlorophyll concentration was {row['chlorophyll']:.3f} mg/m³."
        
        doc = (
            f"On {row['time'].strftime('%Y-%m-%d')}, an observation was made at "
            f"latitude {row['lat']} and longitude {row['lon']}. "
            f"At a depth of {row['depth']} meters, the temperature was {temp_str} "
            f"and the salinity was {sal_str}.{bgc_info}"
        )
        meta = {
            'postgres_id': int(row['id']),
            'time': row['time'].strftime('%Y-%m-%d'),
            'depth': float(row['depth']),
            'lat': float(row['lat']),
            'lon': float(row['lon'])
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

print(f"there are now {collection.count()} documents in the collection")