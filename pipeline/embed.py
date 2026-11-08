"""
Embed profile descriptions, reusing vectors from a cache file for unchanged text.
Embedding thousands of descriptions on a CPU takes minutes; the cache makes a
fresh local install start in seconds.
"""

import hashlib
import os
from pathlib import Path

import numpy as np


def embed_with_cache(docs: list[str], embedder, cache_path: str | Path | None) -> np.ndarray:
    hashes = [hashlib.sha1(doc.encode("utf-8")).hexdigest() for doc in docs]
    cache: dict[str, np.ndarray] = {}
    if cache_path and os.path.exists(cache_path):
        stored = np.load(cache_path)
        cache = dict(zip(stored["hashes"].tolist(), stored["vectors"]))

    missing = [i for i, h in enumerate(hashes) if h not in cache]
    if missing:
        vectors = embedder.embed([docs[i] for i in missing])
        for i, vector in zip(missing, vectors):
            cache[hashes[i]] = np.asarray(vector, dtype=np.float16)
        if cache_path:
            np.savez_compressed(cache_path, hashes=np.array(hashes),
                                vectors=np.stack([cache[h] for h in hashes]))

    if not docs:
        return np.zeros((0, 384), dtype=np.float32)
    return np.stack([cache[h] for h in hashes]).astype(np.float32)
