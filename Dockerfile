FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the ChromaDB embedding model (~80 MB) into the image so first start is fast
RUN python -c "from chromadb.utils import embedding_functions as ef; ef.DefaultEmbeddingFunction()(['warm up'])"

COPY . .

EXPOSE 8000 8501
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
