from __future__ import annotations

import math
import re
from typing import Any

from confidencial_rag.ingestion.base import RAGError
from confidencial_rag.models import DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_PROVIDER, sha256_bytes


class HashEmbeddingProvider:
    provider_name = "hashing"

    def __init__(self, model_name: str = "sha256-hashing-test-v1", dimension: int = 384) -> None:
        self.model_name = model_name
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            row = [0.0] * self.dimension
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                digest = int(sha256_bytes(word.encode("utf-8"))[:16], 16)
                row[digest % self.dimension] += 1.0
            norm = math.sqrt(sum(value * value for value in row)) or 1.0
            vectors.append([value / norm for value in row])
        return vectors


class SentenceTransformersEmbeddingProvider:
    provider_name = DEFAULT_EMBEDDING_PROVIDER

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL, batch_size: int = 32) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.dimension = 384
        self._model: Any | None = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RAGError("sentence-transformers is required for the configured embedding provider.") from exc
        try:
            self._model = SentenceTransformer(self.model_name)
            self.dimension = int(self._model.get_sentence_embedding_dimension())
        except Exception as exc:
            raise RAGError("The configured sentence-transformers embedding model could not be loaded.") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        encoded = self._model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True)
        return [list(map(float, row)) for row in encoded]


__all__ = ["HashEmbeddingProvider", "SentenceTransformersEmbeddingProvider"]
