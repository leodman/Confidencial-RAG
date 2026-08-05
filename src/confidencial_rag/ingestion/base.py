from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from confidencial_rag.models import TextUnit

SUPPORTED_EXTENSIONS = {".txt", ".md", ".qmd", ".html", ".htm", ".json", ".csv", ".pdf", ".docx"}


class RAGError(RuntimeError):
    pass


class DocumentLoader:
    def load_units(self, path: Path) -> tuple[list[TextUnit], dict[str, Any], list[str]]:
        ext = path.suffix.lower()
        data = path.read_bytes()
        if ext not in SUPPORTED_EXTENSIONS:
            raise RAGError("Unsupported file type.")
        try:
            if ext in {".txt", ".md", ".qmd"}:
                units = [TextUnit(data.decode("utf-8"))]
                metadata: dict[str, Any] = {}
            elif ext in {".html", ".htm"}:
                raw = data.decode("utf-8", errors="replace")
                raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
                units = [TextUnit(html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw)))]
                metadata = {}
            elif ext == ".json":
                obj = json.loads(data.decode("utf-8"))
                units = [TextUnit(json.dumps(obj, indent=2, sort_keys=True))]
                metadata = {}
            elif ext == ".csv":
                rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
                units = [TextUnit("\n".join(" | ".join(row) for row in rows))]
                metadata = {}
            elif ext == ".pdf":
                units, metadata = self._load_pdf(path)
            elif ext == ".docx":
                units, metadata = self._load_docx(path)
        except (UnicodeDecodeError, json.JSONDecodeError, csv.Error, KeyError, zipfile.BadZipFile) as exc:
            raise RAGError(f"Could not safely read {ext or 'document'} content.") from exc
        warnings: list[str] = []
        if not any(unit.text.strip() for unit in units):
            if ext == ".pdf":
                warnings.append("No extractable text was found. OCR is not implemented in Version 1.")
            warnings.append("Document is empty after text extraction.")
        return units, metadata, warnings

    def load(self, path: Path, rel: str | None = None) -> tuple[str, dict[str, Any], list[str]]:
        units, metadata, warnings = self.load_units(path)
        return "\n".join(unit.text for unit in units), metadata, warnings

    def _load_pdf(self, path: Path) -> tuple[list[TextUnit], dict[str, Any]]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RAGError("PDF support requires pypdf.") from exc
        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise RAGError("Could not safely read PDF content.") from exc
        units = [TextUnit(page.extract_text() or "", page_number=index) for index, page in enumerate(reader.pages, 1)]
        return units, {"page_count": len(reader.pages)}

    def _load_docx(self, path: Path) -> tuple[list[TextUnit], dict[str, Any]]:
        try:
            from docx import Document
        except ImportError:
            return self._load_docx_xml(path)
        try:
            text = "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)
        except Exception as exc:
            raise RAGError("Could not safely read DOCX content.") from exc
        return [TextUnit(text)], {}

    def _load_docx_xml(self, path: Path) -> tuple[list[TextUnit], dict[str, Any]]:
        import xml.etree.ElementTree as ET

        try:
            with zipfile.ZipFile(path) as zf:
                root = ET.fromstring(zf.read("word/document.xml"))
        except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
            raise RAGError("Could not safely read DOCX content.") from exc
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = []
        for paragraph in root.iter(f"{namespace}p"):
            pieces = [node.text or "" for node in paragraph.iter(f"{namespace}t")]
            if pieces:
                paragraphs.append("".join(pieces))
        return [TextUnit("\n".join(paragraphs))], {}


__all__ = ["DocumentLoader", "RAGError", "SUPPORTED_EXTENSIONS"]
