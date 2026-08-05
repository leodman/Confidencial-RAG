from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


__all__ = ["EmbeddingProvider"]
