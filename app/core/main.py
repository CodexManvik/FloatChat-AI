from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

# Initialize FastAPI app
app = FastAPI(
    title="FloatChat RAG (LangChain + Ollama + Chroma)",
    description="RAG chatbot using LangChain, Ollama LLM, and Chroma vectorstore",
    version="1.0.0",
)

# Include API routes
app.include_router(router, prefix="/api")

# Enable CORS for local frontend development
origins = [
    "http://localhost",
    "http://localhost:3000",  # React frontend default
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional startup event
@app.on_event("startup")
async def startup_event():
    print("🚀 FloatChat RAG app is starting up...")

# Optional shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 FloatChat RAG app is shutting down...")
