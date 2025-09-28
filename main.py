from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
import ollama
import pandas as pd 
from datetime import datetime
from sqlalchemy import create_engine
from export_utils import export_to_ascii, export_to_netcdf, export_to_csv
from fastapi.responses import Response
from nl_to_sql import NLToSQLTranslator, process_analytical_query
import config
import uuid

engine = create_engine(config.DATABASE_URL)

app = FastAPI(
    title="Ocean Data RAG API",
    description="An API to query oceanographic data using natural language with NL-to-SQL capabilities"
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected" if engine else "disconnected",
        "chromadb": "connected" if collection else "disconnected"
    }

# Initialize NL-to-SQL translator
nl_sql_translator = NLToSQLTranslator()

class QueryRequest(BaseModel):
    query_text: str

class QueryResponse(BaseModel):
    answer: str
    context_documents: list[str]
    retrieved_metadata: list[dict]
    sql_results: list[dict] = None  # Optional SQL results for analytical queries

try:
    client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    ollama_ef = embedding_functions.OllamaEmbeddingFunction(
        url=f"{config.OLLAMA_HOST}/api/embeddings",
        model_name=config.EMBEDDING_MODEL
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
async def query_rag_pipeline(request: QueryRequest):
    """
    Enhanced query endpoint that handles both analytical (SQL) and semantic (RAG) queries
    """
    if collection is None:
        return {"answer": "Error: ChromaDB collection not available.", "context_documents": [], "retrieved_metadata": []}
    
    # Check if this is an analytical query that needs SQL
    if nl_sql_translator.is_analytical_query(request.query_text):
        try:
            # Process with enhanced NL-to-SQL
            sql_result, error = process_analytical_query(request.query_text)
            
            if error:
                # Fall back to semantic search if SQL fails
                print(f"SQL processing failed: {error}")
                return await semantic_search_query(request.query_text)
            
            # Extract enhanced SQL results
            sql_query = sql_result['sql_query']
            results_df = sql_result['results']
            intent = sql_result['intent']
            summary_stats = sql_result['summary_stats']
            
            if results_df.empty:
                answer = f"Your analytical query executed successfully but returned no results. This might mean the data doesn't match your criteria. SQL executed: {sql_query}"
                return {
                    "answer": answer, 
                    "context_documents": [f"SQL Query: {sql_query}"], 
                    "retrieved_metadata": [{"query_type": "analytical", "intent": intent, "status": "no_results"}]
                }
            
            # Generate a simple summary without LLM (faster)
            results_preview = results_df.head(5).to_string(index=False)
            
            # Create a readable, formatted summary
            def format_results_for_display(df, intent_type):
                """Format results in a human-readable way based on query intent"""
                
                if intent_type == 'avg_by_depth':
                    formatted_text = "**Temperature and Salinity by Depth Analysis:**\n\n"
                    for _, row in df.head(10).iterrows():
                        depth = f"{row['depth']:.0f}m"
                        temp = f"{row['avg_temperature']:.2f}°C" if pd.notna(row['avg_temperature']) else "N/A"
                        sal = f"{row['avg_salinity']:.2f} PSU" if pd.notna(row['avg_salinity']) else "N/A"
                        count = f"{row['measurement_count']:.0f}" if pd.notna(row['measurement_count']) else "0"
                        formatted_text += f"• **{depth} depth**: Temperature {temp}, Salinity {sal} ({count} measurements)\n"
                    
                elif intent_type == 'regional_comparison':
                    formatted_text = "**Regional Ocean Analysis:**\n\n"
                    for _, row in df.iterrows():
                        region = row.get('region', 'Unknown Region')
                        temp = f"{row['avg_temperature']:.2f}°C" if pd.notna(row['avg_temperature']) else "N/A"
                        sal = f"{row['avg_salinity']:.2f} PSU" if pd.notna(row['avg_salinity']) else "N/A"
                        count = f"{row['measurement_count']:.0f}" if pd.notna(row['measurement_count']) else "0"
                        formatted_text += f"• **{region}**: Avg Temperature {temp}, Avg Salinity {sal} ({count} measurements)\n"
                
                elif intent_type == 'temporal_trends':
                    formatted_text = "**Temporal Ocean Trends:**\n\n"
                    for _, row in df.head(10).iterrows():
                        month = row['month'].strftime('%B %Y') if hasattr(row['month'], 'strftime') else str(row['month'])
                        temp = f"{row['avg_temperature']:.2f}°C" if pd.notna(row['avg_temperature']) else "N/A"
                        sal = f"{row['avg_salinity']:.2f} PSU" if pd.notna(row['avg_salinity']) else "N/A"
                        count = f"{row['measurement_count']:.0f}" if pd.notna(row['measurement_count']) else "0"
                        formatted_text += f"• **{month}**: Temperature {temp}, Salinity {sal} ({count} measurements)\n"
                
                elif intent_type == 'float_summary':
                    formatted_text = "**ARGO Float Performance Summary:**\n\n"
                    for _, row in df.head(10).iterrows():
                        float_id = row['float_id']
                        profiles = f"{row['total_profiles']:.0f}" if pd.notna(row['total_profiles']) else "0"
                        measurements = f"{row['total_measurements']:.0f}" if pd.notna(row['total_measurements']) else "0"
                        temp = f"{row['avg_temperature']:.2f}°C" if pd.notna(row['avg_temperature']) else "N/A"
                        depth_range = f"{row['min_depth']:.0f}-{row['max_depth']:.0f}m" if pd.notna(row['min_depth']) else "N/A"
                        formatted_text += f"• **{float_id}**: {profiles} profiles, {measurements} measurements, Avg temp {temp}, Depth range {depth_range}\n"
                
                else:
                    # Generic formatting for other query types
                    formatted_text = "**Analysis Results:**\n\n"
                    for i, (_, row) in enumerate(df.head(10).iterrows()):
                        formatted_text += f"**Result {i+1}:**\n"
                        for col, val in row.items():
                            if pd.notna(val):
                                if 'temperature' in col.lower():
                                    formatted_text += f"  - {col.replace('_', ' ').title()}: {val:.2f}°C\n"
                                elif 'salinity' in col.lower():
                                    formatted_text += f"  - {col.replace('_', ' ').title()}: {val:.2f} PSU\n"
                                elif 'depth' in col.lower():
                                    formatted_text += f"  - {col.replace('_', ' ').title()}: {val:.0f}m\n"
                                elif 'count' in col.lower():
                                    formatted_text += f"  - {col.replace('_', ' ').title()}: {val:.0f}\n"
                                else:
                                    formatted_text += f"  - {col.replace('_', ' ').title()}: {val}\n"
                        formatted_text += "\n"
                
                return formatted_text
            
            # Generate readable summary
            formatted_results = format_results_for_display(results_df, intent)
            
            answer = f"""**Analytical Query Results**

**Query:** {request.query_text}
**Analysis Type:** {intent.replace('_', ' ').title()}
**Total Results:** {len(results_df)} data points

{formatted_results}

**Key Insights:**
- Data spans {len(results_df)} measurements from ARGO float observations
- Analysis covers temperature, salinity, and depth relationships
- Results show oceanographic patterns in the selected region

*Note: This analysis is based on ARGO float data from the Indian Ocean region.*"""
            
            # Enhanced metadata for frontend (ensure JSON serializable)
            sql_metadata = [{
                'query_type': 'analytical',
                'intent': str(intent),
                'sql_query': str(sql_query),
                'row_count': int(len(results_df)),
                'column_count': int(len(results_df.columns)),
                'columns': [str(col) for col in results_df.columns],
                'execution_status': str(sql_result['execution_status']),
                'summary_stats': summary_stats
            }]
            
            # Convert DataFrame to JSON-serializable format
            def convert_numpy_types(obj):
                """Convert numpy types to Python native types"""
                if hasattr(obj, 'dtype'):
                    if 'int' in str(obj.dtype):
                        return int(obj)
                    elif 'float' in str(obj.dtype):
                        return float(obj)
                    elif 'bool' in str(obj.dtype):
                        return bool(obj)
                    else:
                        return str(obj)
                return obj
            
            # Limit results and convert numpy types
            limited_df = results_df.head(200) if len(results_df) > 200 else results_df
            limited_results = []
            
            for _, row in limited_df.iterrows():
                row_dict = {}
                for col, val in row.items():
                    if pd.isna(val):
                        row_dict[str(col)] = None
                    else:
                        row_dict[str(col)] = convert_numpy_types(val)
                limited_results.append(row_dict)
            
            return {
                "answer": answer,
                "context_documents": [f"SQL Analysis ({intent}): {sql_query}"],
                "retrieved_metadata": sql_metadata,
                "sql_results": limited_results
            }
            
        except (TimeoutError, Exception) as e:
            print(f"SQL processing error: {e}")
            # Fall back to semantic search for any error including timeouts
            return await semantic_search_query(request.query_text)
    
    else:
        # Use semantic search for descriptive queries
        return await semantic_search_query(request.query_text)

async def semantic_search_query(query_text: str):
    """Handle semantic search queries using ChromaDB"""
    
    results = collection.query(
        query_texts=[query_text],
        n_results=5
    )

    retrieved_documents = results['documents'][0]
    retrieved_metadata = results['metadatas'][0]
    context = "\n".join(retrieved_documents)

    prompt = f"""
    You are an expert oceanographic AI assistant.
    Your task is to answer the user's question using only the facts present in the provided Context.
    Be concise and factual. If the information is not in the context, say so.

    Context:
    {context}

    Question:
    {query_text}

    Answer:
    """

    response = ollama.chat(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    answer = response["message"]["content"]

    return {
        "answer": answer,
        "context_documents": retrieved_documents,
        "retrieved_metadata": retrieved_metadata
    }

class ProfileRequest(BaseModel):
    ids: list[int]

class ExportRequest(BaseModel):
    format: str  # "ascii", "netcdf", "csv"
    data_ids: list[int]

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
    data for each ID from the PostgreSQL database with float context.
    """
    if not request.ids:
        return []
    
    if engine is None:
        return {"error": "Database connection not available"}

    # Format the list of IDs for the SQL query
    ids_tuple = tuple(request.ids)
    
    # Enhanced query with float and profile context
    sql_query = """
    SELECT 
        m.id, m.time, m.lat, m.lon, m.depth, m.temperature, m.salinity,
        m.oxygen, m.ph, m.chlorophyll, m.float_id, m.profile_id,
        p.cycle_number, f.wmo_id
    FROM measurements m
    JOIN profiles p ON m.profile_id = p.profile_id  
    JOIN floats f ON m.float_id = f.float_id
    WHERE m.id IN %s
    ORDER BY m.float_id, p.cycle_number, m.depth;
    """
    
    try:
        # Execute the query and load results into a DataFrame
        df = pd.read_sql_query(sql_query, engine, params=(ids_tuple,))
        
        # Convert DataFrame to a list of dictionaries to match the Pydantic model
        return df.to_dict(orient='records')
        
    except Exception as e:
        print(f"Error querying PostgreSQL: {e}")
        return []

@app.get("/float/{float_id}")
async def get_float_info(float_id: str):
    """Get comprehensive information about a specific ARGO float"""
    
    try:
        # Get float basic info
        float_sql = "SELECT * FROM floats WHERE float_id = %s;"
        float_df = pd.read_sql_query(float_sql, engine, params=(float_id,))
        
        if float_df.empty:
            return {"error": "Float not found"}
        
        # Get profile summary
        profiles_sql = """
        SELECT COUNT(*) as total_profiles, 
               MIN(profile_date) as first_profile,
               MAX(profile_date) as last_profile,
               COUNT(DISTINCT DATE(profile_date)) as active_days
        FROM profiles WHERE float_id = %s;
        """
        profile_summary = pd.read_sql_query(profiles_sql, engine, params=(float_id,))
        
        # Get measurement summary  
        measurements_sql = """
        SELECT COUNT(*) as total_measurements,
               MIN(depth) as min_depth,
               MAX(depth) as max_depth,
               AVG(temperature) as avg_temp,
               AVG(salinity) as avg_sal
        FROM measurements WHERE float_id = %s;
        """
        measurement_summary = pd.read_sql_query(measurements_sql, engine, params=(float_id,))
        
        return {
            "float_info": float_df.to_dict(orient='records')[0],
            "profile_summary": profile_summary.to_dict(orient='records')[0],
            "measurement_summary": measurement_summary.to_dict(orient='records')[0]
        }
        
    except Exception as e:
        return {"error": f"Failed to get float info: {str(e)}"}

@app.get("/profiles/float/{float_id}")
async def get_float_profiles(float_id: str):
    """Get all profiles for a specific float"""
    
    try:
        sql_query = """
        SELECT p.*, 
               COUNT(m.id) as measurement_count,
               AVG(m.temperature) as avg_temp,
               AVG(m.salinity) as avg_sal,
               MIN(m.depth) as min_depth,
               MAX(m.depth) as max_depth
        FROM profiles p
        LEFT JOIN measurements m ON p.profile_id = m.profile_id
        WHERE p.float_id = %s
        GROUP BY p.profile_id
        ORDER BY p.cycle_number;
        """
        
        df = pd.read_sql_query(sql_query, engine, params=(float_id,))
        return df.to_dict(orient='records')
        
    except Exception as e:
        return {"error": f"Failed to get profiles: {str(e)}"}

@app.post("/export")
async def export_data(request: ExportRequest):
    """
    Export ARGO data in specified format (ASCII, NetCDF, CSV)
    """
    try:
        if request.format.lower() == "ascii":
            content = export_to_ascii(request.data_ids)
            return Response(
                content=content,
                media_type="text/plain",
                headers={"Content-Disposition": "attachment; filename=argo_data.txt"}
            )
        elif request.format.lower() == "netcdf":
            content = export_to_netcdf(request.data_ids)
            return Response(
                content=content,
                media_type="application/octet-stream",
                headers={"Content-Disposition": "attachment; filename=argo_data.nc"}
            )
        elif request.format.lower() == "csv":
            content = export_to_csv(request.data_ids)
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=argo_data.csv"}
            )
        else:
            return {"error": "Unsupported format. Use 'ascii', 'netcdf', or 'csv'"}
    
    except Exception as e:
        return {"error": f"Export failed: {str(e)}"}

@app.get("/sample-queries")
async def get_sample_queries():
    """Get comprehensive sample queries organized by category"""
    from nl_to_sql import get_sample_analytical_queries
    
    analytical_queries = get_sample_analytical_queries()
    
    # Add extensibility-focused queries
    analytical_queries["Multi-Dataset Analysis"] = [
        "Compare ARGO floats with glider observations",
        "Show satellite vs in-situ temperature differences", 
        "Analyze buoy and float data in the same region",
        "Cross-validate different sensor platforms"
    ]
    
    semantic_queries = {
        "Current Data (ARGO)": [
            "Show me temperature measurements near the equator",
            "Tell me about salinity profiles in deep water",
            "What ARGO floats are active in the Indian Ocean?",
            "Find measurements with high oxygen levels"
        ],
        
        "Future Capabilities": [
            "How would glider data complement ARGO observations?",
            "What advantages do satellite measurements provide?",
            "Explain the role of moored buoys in ocean monitoring",
            "Describe BGC sensor capabilities across platforms"
        ],
        
        "Contextual Queries": [
            "How do different platforms collect ocean data?",
            "What is the significance of multi-platform validation?",
            "Tell me about ocean observation networks",
            "Explain the importance of data integration"
        ]
    }
    
    return {
        "analytical_queries": analytical_queries,
        "semantic_queries": semantic_queries,
        "extensibility_info": {
            "current_datasets": ["ARGO Floats"],
            "planned_datasets": ["Gliders", "Buoys", "Satellites"],
            "integration_ready": True
        },
        "query_tips": {
            "analytical": "Use words like 'average', 'compare', 'count', 'trend' for statistical analysis",
            "semantic": "Ask descriptive questions about specific measurements or oceanographic concepts",
            "multi_dataset": "Future: Compare different platforms using 'compare X with Y' or 'validate X against Y'"
        }
    }

@app.get("/extensibility/status")
async def get_extensibility_status():
    """Get current extensibility status and future dataset support"""
    
    return {
        "current_status": "Extensibility Framework Ready",
        "supported_datasets": {
            "implemented": ["ARGO Floats"],
            "framework_ready": ["Gliders", "Buoys", "Satellites", "Custom Datasets"]
        },
        "capabilities": {
            "unified_schema": "Ready for multi-dataset storage",
            "cross_platform_queries": "NL-to-SQL supports multi-dataset analysis", 
            "visualization_framework": "Adaptable to different data types",
            "export_system": "Supports multiple formats for any dataset"
        },
        "integration_points": {
            "data_ingestion": "Pluggable processor architecture",
            "query_system": "Template-based extensibility",
            "visualization": "Configurable chart types per dataset",
            "metadata": "Unified platform and observation tables"
        },
        "next_steps": [
            "Implement glider data processor",
            "Add satellite data ingestion",
            "Create buoy data handlers", 
            "Develop cross-platform validation queries"
        ]
    }

@app.get("/nl-sql/test")
async def test_nl_sql_system():
    """Test endpoint for NL-to-SQL system validation"""
    try:
        from nl_to_sql import NLToSQLTranslator
        
        translator = NLToSQLTranslator()
        
        # Test a simple query
        query = "What is the average temperature at different depths?"
        intent = translator.detect_query_intent(query)
        
        if intent in translator.query_templates:
            sql = translator.query_templates[intent]
            
            # Test SQL execution
            result_df, status = translator.execute_sql_query(sql)
            
            return {
                "status": "success",
                "intent": intent,
                "sql_preview": sql[:200] + "...",
                "result_rows": len(result_df),
                "execution_status": status,
                "system_ready": True
            }
        else:
            return {
                "status": "no_template",
                "intent": intent,
                "system_ready": False
            }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "system_ready": False
        }

@app.post("/query-simple")
async def simple_query(request: QueryRequest):
    """Simplified query endpoint for testing"""
    try:
        from nl_to_sql import NLToSQLTranslator
        
        translator = NLToSQLTranslator()
        
        # Check if analytical
        if translator.is_analytical_query(request.query_text):
            intent = translator.detect_query_intent(request.query_text)
            
            if intent in translator.query_templates:
                sql = translator.query_templates[intent]
                result_df, status = translator.execute_sql_query(sql)
                
                return {
                    "answer": f"Executed SQL query with {len(result_df)} results",
                    "context_documents": [f"SQL: {sql[:100]}..."],
                    "retrieved_metadata": [{"query_type": "analytical", "intent": intent}],
                    "sql_results": result_df.head(10).to_dict('records') if not result_df.empty else []
                }
        
        # Fall back to semantic search
        return await semantic_search_query(request.query_text)
        
    except Exception as e:
        return {
            "answer": f"Error: {str(e)}",
            "context_documents": [],
            "retrieved_metadata": []
        }
