"""Test doubles shared by unit and integration tests."""

import hashlib

import numpy as np


class FakeEmbedder:
    """Deterministic 384-d unit vectors derived from the text hash; no model download."""

    dims = 384

    def __init__(self):
        self.calls = 0

    def embed(self, texts, batch_size=64, pad_to=None):
        self.calls += 1
        out = np.zeros((len(texts), self.dims), dtype=np.float32)
        for i, text in enumerate(texts):
            seed = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
            vector = np.random.default_rng(seed).standard_normal(self.dims).astype(np.float32)
            out[i] = vector / np.linalg.norm(vector)
        return out
