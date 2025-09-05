# ARGO NetCDF RAG Pipeline

## What This Does
- Processes ARGO oceanographic NetCDF data (645 profiles)
- Stores in PostgreSQL (relational) + Chroma (vector database)  
- Provides RAG-based natural language queries about ocean data
- Web interface for interactive queries

## Files
- `nc_to_dataframe.py` - Converts NetCDF to DataFrame
- `to_postgres.py` - PostgreSQL storage
- `to_chroma.py` - Chroma vector indexing
- `pipeline.py` - Complete end-to-end pipeline
- `rag_query.py` - RAG query system  
- `web_app.py` - Flask web interface
- `templates/index.html` - Web UI

## Quick Start
1. Install: `pip install netCDF4 pandas sqlalchemy psycopg2-binary chromadb sentence-transformers flask`
2. Setup: Copy `.env.example` to `.env` and add PostgreSQL credentials
3. Run: `python pipeline.py` then `python web_app.py`
4. Access: http://localhost:5000

## Demo Queries
- "What is the temperature in tropical waters?"
- "Show me salinity data from the Indian Ocean"
- "Where are the warmest ocean temperatures?"

Successfully processes 645 real ARGO ocean profiles! 🌊
