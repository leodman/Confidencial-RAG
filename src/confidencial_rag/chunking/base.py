from __future__ import annotations

import re

from confidencial_rag.ingestion.base import RAGError
from confidencial_rag.models import ChunkRecord, DocumentRecord, TextUnit, sha256_bytes, stable_id


class RecursiveChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150) -> None:
        if not 100 <= chunk_size <= 4000 or not 0 <= chunk_overlap < chunk_size:
            raise RAGError("Invalid chunk settings.")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunks(self, document: DocumentRecord, units: list[TextUnit] | str) -> list[ChunkRecord]:
        if isinstance(units, str):
            units = [TextUnit(units)]
        chunks: list[ChunkRecord] = []
        for unit in units:
            chunks.extend(self._chunk_unit(document, unit, len(chunks)))
        return chunks

    def _chunk_unit(self, document: DocumentRecord, unit: TextUnit, start_index: int) -> list[ChunkRecord]:
        text = unit.text
        output: list[ChunkRecord] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            cut = self._best_cut(text, start, end)
            segment = text[start:cut].strip()
            if segment:
                section = unit.section or self._detect_section(segment)
                content_hash = sha256_bytes(segment.encode("utf-8"))
                index = start_index + len(output)
                chunk_id = stable_id("chk", document.document_id, str(index), content_hash)
                output.append(
                    ChunkRecord(
                        chunk_id=chunk_id,
                        document_id=document.document_id,
                        text=segment,
                        chunk_index=index,
                        page_number=unit.page_number,
                        section=section,
                        source_path=document.relative_path,
                        character_start=start,
                        character_end=cut,
                        content_hash=content_hash,
                    )
                )
            if cut >= len(text):
                break
            start = max(cut - self.chunk_overlap, start + 1)
        return output

    def _best_cut(self, text: str, start: int, end: int) -> int:
        for pattern in ("\n#", "\n\n", ". ", " "):
            index = text.rfind(pattern, start, end)
            if index > start + self.chunk_size // 2:
                return index + len(pattern)
        return end

    def _detect_section(self, segment: str) -> str | None:
        match = re.search(r"(?m)^#+\s+(.+)$", segment)
        return match.group(1) if match else None


__all__ = ["RecursiveChunker"]
