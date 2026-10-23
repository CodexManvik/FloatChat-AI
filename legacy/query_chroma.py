import chromadb
from chromadb.utils import embedding_functions

client = chromadb.PersistentClient(path="./chroma_db")

ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text"
)

collection = client.get_collection(
    name="argo_measurements",
    embedding_function=ollama_ef
)

query_text= str(input("enter query: "))

results = collection.query(
    query_texts=[query_text],
    n_results=5
)

print(f"Query: {query_text}\n")
print("--- Top 5 Results ---")
for i, doc in enumerate(results['documents'][0]):
    metadata = results['metadatas'][0][i]
    distance = results['distances'][0][i]
    
    print(f"Result {i+1} (Distance: {distance:.4f}):")
    print(f"  Document: {doc}")
    print(f"  Metadata: {metadata}\n")