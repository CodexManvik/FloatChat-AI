import numpy as np

from pipeline.embed import embed_with_cache
from tests.fakes import FakeEmbedder


def test_embeds_without_cache():
    embedder = FakeEmbedder()
    vectors = embed_with_cache(["a", "b"], embedder, None)
    assert vectors.shape == (2, 384) and vectors.dtype == np.float32
    assert embedder.calls == 1


def test_cache_roundtrip(tmp_path):
    cache = tmp_path / "cache.npz"
    first = embed_with_cache(["a", "b"], FakeEmbedder(), cache)
    assert cache.exists()
    embedder = FakeEmbedder()
    second = embed_with_cache(["b", "a"], embedder, cache)
    assert embedder.calls == 0  # everything came from the cache
    assert np.allclose(second[0], first[1], atol=1e-3)  # float16 storage


def test_only_new_documents_are_embedded(tmp_path):
    cache = tmp_path / "cache.npz"
    embed_with_cache(["a"], FakeEmbedder(), cache)
    embedder = FakeEmbedder()
    embed_with_cache(["a", "c"], embedder, cache)
    assert embedder.calls == 1
