from __future__ import annotations

import re
from typing import Any

from confidencial_rag.ingestion.base import RAGError
from confidencial_rag.models import ChunkRecord


class ExtractiveLLM:
    def generate(self, question: str, results: list[tuple[ChunkRecord, float]], citations: list[dict[str, Any]]) -> str:
        if not results:
            return "I could not find sufficient evidence in the indexed documents."
        seen: set[str] = set()
        lines = ["Based on the strongest indexed evidence:"]
        for citation, (chunk, _score) in zip(citations, results):
            normalized = re.sub(r"\s+", " ", chunk.text).strip()
            if not normalized or normalized[:160] in seen:
                continue
            seen.add(normalized[:160])
            lines.append(f"- {normalized[:450]} [{citation['number']}]")
            if len(lines) >= 4:
                break
        return "\n".join(lines) if len(lines) > 1 else "I could not find sufficient evidence in the indexed documents."


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None) -> None:
        if not api_key:
            raise RAGError("An API key is required for external generation.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.last_payload: dict[str, str] | None = None

    def generate(self, question: str, results: list[tuple[ChunkRecord, float]], citations: list[dict[str, Any]]) -> str:
        from openai import OpenAI

        context = "\n\n".join(f"[{citation['number']}] {chunk.text}" for citation, (chunk, _score) in zip(citations, results))
        prompt = (
            "Answer only from supplied context. State if context is insufficient. Do not invent facts. "
            "Preserve placeholder tokens exactly and cite sources using supplied citation identifiers.\n"
            f"Context:\n{context}\nQuestion: {question}"
        )
        self.last_payload = {"question": question, "context": context}
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or ""


__all__ = ["ExtractiveLLM", "OpenAIProvider"]
