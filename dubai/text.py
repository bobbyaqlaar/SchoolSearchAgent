"""Semantic text utilities. Sentence-transformer model is loaded lazily so
importing this module stays cheap (and unit tests can stub the encoder)."""

from __future__ import annotations

import logging

import numpy as np

logging.getLogger("transformers").setLevel(logging.ERROR)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def cosine_similarity(sentence1: str, sentence2: str) -> float:
    """Cosine similarity in [0, 1] between two sentences' embeddings."""
    embeddings = _get_model().encode([sentence1, sentence2])
    a, b = np.asarray(embeddings[0]), np.asarray(embeddings[1])
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    similarity = float(np.dot(a, b) / denom)
    return float(np.clip(similarity, 0.0, 1.0))
