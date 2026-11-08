"""
Sentence embeddings with all-MiniLM-L6-v2 (ONNX), the same model ChromaDB used.

Each batch is padded only to its longest text instead of a fixed 256 tokens,
so a short question embeds in milliseconds even on a tiny CPU.
"""

import hashlib
import tarfile
import tempfile
import threading
from pathlib import Path

import numpy as np
import requests

from floatchat import config

MODEL_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
MODEL_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
DIMENSIONS = 384
MAX_TOKENS = 256


def ensure_model(model_dir: Path) -> Path:
    """Download and unpack the model once; returns the folder holding model.onnx."""
    target = model_dir / "onnx"
    if (target / "model.onnx").exists() and (target / "tokenizer.json").exists():
        return target
    model_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=model_dir) as tmp:
        archive = Path(tmp) / "onnx.tar.gz"
        digest = hashlib.sha256()
        with requests.get(MODEL_URL, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(archive, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    f.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise RuntimeError("Embedding model download failed its SHA-256 check")
        with tarfile.open(archive) as tar:
            _safe_extract(tar, model_dir)
    return target


def _safe_extract(tar: tarfile.TarFile, target: Path) -> None:
    try:
        tar.extractall(target, filter="data")
        return
    except TypeError:
        pass  # Python < 3.11.4 has no extraction filters: check members ourselves
    root = target.resolve()
    for member in tar.getmembers():
        destination = (target / member.name).resolve()
        inside = destination == root or root in destination.parents
        if not inside or not (member.isfile() or member.isdir()):
            raise RuntimeError(f"Unsafe entry in model archive: {member.name}")
    tar.extractall(target)


class Embedder:
    def __init__(self, model_dir: Path | None = None):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        folder = ensure_model(Path(model_dir or config.MODEL_DIR))
        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=MAX_TOKENS)
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self._session = ort.InferenceSession(str(folder / "model.onnx"), sess_options=options,
                                             providers=["CPUExecutionProvider"])
        self._lock = threading.Lock()  # the tokenizer's padding setting is shared state

    def embed(self, texts: list[str], batch_size: int = 64, pad_to: int | None = None) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIMENSIONS), dtype=np.float32)
        out = []
        with self._lock:
            if pad_to:
                self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=pad_to)
            else:
                self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
            for i in range(0, len(texts), batch_size):
                encodings = self._tokenizer.encode_batch(texts[i:i + batch_size])
                ids = np.array([e.ids for e in encodings], dtype=np.int64)
                mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
                hidden = self._session.run(None, {"input_ids": ids, "attention_mask": mask,
                                                  "token_type_ids": np.zeros_like(ids)})[0]
                weights = mask[..., None].astype(np.float32)
                pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
                norms = np.linalg.norm(pooled, axis=1, keepdims=True)
                norms[norms == 0] = 1e-12
                out.append((pooled / norms).astype(np.float32))
        return np.concatenate(out)


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            _embedder = Embedder()
        return _embedder
