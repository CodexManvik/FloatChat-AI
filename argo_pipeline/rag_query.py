# rag_query.py - Query your ARGO data using RAG
import chromadb
from sentence_transformers import SentenceTransformer
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

class ArgoRAG:
    def __init__(self):
        print("🚀 Initializing ARGO RAG System...")
        
        # Initialize Chroma client
        self.chroma_client = chromadb.PersistentClient(path="./chroma_store")
        self.collection = self.chroma_client.get_collection("argo_profiles")
        
        # Initialize embedding model
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # PostgreSQL connection
        self.db_url = os.getenv("DATABASE_URL")
        print("✅ RAG System ready!")
    
    def semantic_search(self, query: str, n_results: int = 5):
        """
        Perform semantic search using Chroma vector database
        """
        print(f"🔍 Searching: '{query}'")
        
        # Embed the query
        query_embedding = self.model.encode([query]).tolist()
        
        # Search in Chroma
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        
        return results
    
    def sql_query(self, sql: str):
        """
        Execute SQL query on PostgreSQL
        """
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute(sql)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return results, columns
        except Exception as e:
            print(f"SQL Error: {e}")
            return None, None
    
    def answer_question(self, question: str):
        """
        Answer questions about ARGO data using RAG approach
        """
        print(f"\n❓ Question: {question}")
        print("-" * 50)
        
        # Step 1: Vector search for relevant profiles
        results = self.semantic_search(question, n_results=3)
        
        print("📊 Most relevant profiles:")
        context_info = []
        for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
            info = f"Profile {metadata['float_id']}: {metadata['latitude']:.1f}°N, {metadata['longitude']:.1f}°E, Temp: {metadata['surface_temp']:.1f}°C, Sal: {metadata['surface_sal']:.1f}"
            context_info.append(info)
            print(f"{i+1}. {info}")
        
        # Step 2: Generate natural language answer
        answer = self.generate_answer(question, context_info, results['metadatas'][0])
        print(f"\n💬 Answer: {answer}")
        
        return answer
    
    def generate_answer(self, question: str, context_info: list, metadata_list: list):
        """
        Generate natural language answer based on retrieved data
        """
        question_lower = question.lower()
        
        if "temperature" in question_lower:
            temps = [float(m['surface_temp']) for m in metadata_list]
            avg_temp = sum(temps) / len(temps)
            max_temp = max(temps)
            min_temp = min(temps)
            return f"Based on {len(temps)} relevant profiles, temperatures range from {min_temp:.1f}°C to {max_temp:.1f}°C, with an average of {avg_temp:.1f}°C."
        
        elif "salinity" in question_lower:
            sals = [float(m['surface_sal']) for m in metadata_list]
            avg_sal = sum(sals) / len(sals)
            return f"Salinity measurements show an average of {avg_sal:.1f} PSU across {len(sals)} profiles."
        
        elif "location" in question_lower or "where" in question_lower:
            locations = [(float(m['latitude']), float(m['longitude'])) for m in metadata_list]
            return f"Data found at locations: " + ", ".join([f"{lat:.1f}°N {lon:.1f}°E" for lat, lon in locations])
        
        else:
            return f"Found {len(metadata_list)} relevant ARGO profiles. " + " ".join(context_info[:2])

# Demo queries
def demo_queries():
    """
    Demonstrate RAG system with sample queries
    """
    rag = ArgoRAG()
    
    demo_questions = [
        "What is the temperature in tropical waters?",
        "Show me salinity data from the Indian Ocean", 
        "Where are the warmest ocean temperatures?",
        "What are the recent temperature measurements?",
        "Find data with high salinity values"
    ]
    
    print("🌊 ARGO RAG System Demo")
    print("=" * 60)
    
    for question in demo_questions:
        rag.answer_question(question)
        print("\n" + "="*60)

if __name__ == "__main__":
    demo_queries()
