from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
import ollama
import pandas as pd 
from datetime import datetime
from sqlalchemy import create_engine
from urllib.parse import quote_plus

password = quote_plus("Manvik@2005")
engine = create_engine(f"postgresql+psycopg2://postgres:{password}@localhost:5432/argo")

app = FastAPI(
    title="Ocean Data RAG API",
    description="An API to query oceanographic data using natural language"
)

class QueryRequest(BaseModel):
    query_text: str

class QueryResponse(BaseModel):
    answer: str
    context_documents: list[str]
    retrieved_metadata: list[dict]

try:
    client = chromadb.PersistentClient(path="./chroma_db")
    ollama_ef = embedding_functions.OllamaEmbeddingFunction(
        url = "http://localhost:11434/api/embeddings",
        model_name = "nomic-embed-text"
    )
    collection = client.get_collection(
        name="argo_measurements",
        embedding_function=ollama_ef
    )
    print("successfully connected to chromadb collection")
except Exception as e:
    print(f"failed to connect to chromadb: {e}")
    collection = None

@app.post("/query", response_model=QueryResponse)
async def query_rag_pipeline(request:QueryRequest):
    """
    Recieves a natural language query and return an AI-generated answer
    based on retrieved context from the ocean data.
    """
    if collection is None:
        return {"answer":"Error:ChromaDB collection not availabe.","context_documents":[],"retrieved_metadat":[]}
    
    results = collection.query(
        query_texts = [request.query_text],
        n_results=5
    )

    retrieved_documents = results['documents'][0]
    retrieved_metadata = results['metadatas'][0]
    context = "\n".join(retrieved_documents)

    prompt = f"""
        You are an expert oceanographic AI assistant.
        Your task is to answer the user's question using only the facts present in the provided `Context`.
        Be concise and factual. If the information is not in the context, say so.

        Context:
        {context}

        Question:
        {request.query_text}

        Answer:
        """

    response = ollama.chat(
        model = "phi3:mini",
        messages = [{"role":"user", "content":prompt}]
    )

    answer = response["message"]["content"]

    return {"answer":answer,"context_documents":retrieved_documents,"retrieved_metadata":retrieved_metadata}

class ProfileRequest(BaseModel):
    ids: list[int]

# Pydantic model for a single row of measurement data
class Measurement(BaseModel):
    id: int
    time: datetime
    depth: float
    lat: float
    lon: float
    temperature: float | None # Allow for null values
    salinity: float | None    # Allow for null values

# The new endpoint
@app.post("/get_profiles", response_model=list[Measurement])
async def get_profiles_by_ids(request: ProfileRequest):
    """
    Receives a list of postgres_ids and returns the full measurement
    data for each ID from the PostgreSQL database.
    """
    if not request.ids:
        return []
    
    if engine is None:
        return {"error": "Database connection not available"}

    # Format the list of IDs for the SQL query
    ids_tuple = tuple(request.ids)
    
    # Construct the SQL query
    sql_query = "SELECT * FROM measurements WHERE id IN %s;"
    
    try:
        # Execute the query and load results into a DataFrame
        df = pd.read_sql_query(sql_query, engine, params=(ids_tuple,))
        
        # Convert DataFrame to a list of dictionaries to match the Pydantic model
        return df.to_dict(orient='records')
        
    except Exception as e:
        print(f"Error querying PostgreSQL: {e}")
        return []
