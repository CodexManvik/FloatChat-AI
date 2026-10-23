# Legacy scripts

Earlier experiments kept for reference. They are **not** used by the app:

- `data.py`, `data_postgresql.py` – first loaders for the gridded `tempsal.nc` file
- `argo_float_processor.py` – turned the gridded file into "virtual floats" with simulated BGC values
- `data_chroma.py`, `data_chroma_floats.py`, `query_chroma.py` – first ChromaDB indexing/query experiments
- `extensibility_framework.py`, `demo_extensibility.py` – sketch of a multi-dataset (gliders, buoys, satellites) framework

The current pipeline is `scripts/fetch_argo_data.py` (download real ARGO data) → `ingest.py` (PostgreSQL + ChromaDB).
They expect the old `tempsal.nc` file and the old schema; run them from the repo root as modules, e.g. `python -m legacy.query_chroma`.
