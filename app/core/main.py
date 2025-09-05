from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

# ------------------------------
# Create FastAPI app
# ------------------------------
app = FastAPI(
    title="FloatChat RAG (LangChain + Ollama + Chroma)",
    description="Interactive ocean data assistant using RAG and Ollama embeddings",
    version="1.0.0",
)

# ------------------------------
# Enable CORS for local frontend
# ------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Include API routes
# ------------------------------
app.include_router(router, prefix="/api")

# ------------------------------
# Startup event
# ------------------------------
@app.on_event("startup")
async def startup_event():
    print("🚀 FloatChat RAG app is starting up...")
    print("✅ API routes available at: /api")
    print("📄 Swagger docs available at: /docs")
