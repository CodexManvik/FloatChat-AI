import numpy as np
import pytest

from floatchat.embedder import DIMENSIONS, get_embedder

TEXTS = [
    "salinity near the equator",
    "ARGO float 2902203 (WMO 2902203) profile cycle 45 on 11 February 2024 at 12.30°N, 65.20°E in the Arabian Sea.",
]


@pytest.mark.model
def test_dynamic_padding_matches_fixed_padding():
    embedder = get_embedder()
    dynamic = embedder.embed(TEXTS)
    fixed = embedder.embed(TEXTS, pad_to=256)
    assert dynamic.shape == (2, DIMENSIONS)
    cosine = (dynamic * fixed).sum(axis=1)
    assert np.allclose(cosine, 1.0, atol=1e-4)


@pytest.mark.model
def test_vectors_are_normalised_and_distinct():
    vectors = get_embedder().embed(TEXTS)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
    assert float(vectors[0] @ vectors[1]) < 0.95


@pytest.mark.model
def test_empty_input():
    assert get_embedder().embed([]).shape == (0, DIMENSIONS)
