from __future__ import annotations

import copy
import csv
import html
import io
import json
import math
import re
import shutil
import stat
import tempfile
import zipfile
from collections import Counter
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Protocol
from uuid import UUID

from .models import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    KB_FORMAT,
    KB_FORMAT_VERSION,
    ChunkRecord,
    DocumentRecord,
    KnowledgeBase,
    TextUnit,
    sha256_bytes,
    stable_id,
)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".qmd", ".html", ".htm", ".json", ".csv", ".pdf", ".docx"}
REQUIRED_PACKAGE_FILES = {
    "manifest.json",
    "documents.json",
    "chunks.jsonl",
    "configuration.json",
    "README.txt",
    "vectors/index.json",
    "vectors/metadata.json",
}
PROHIBITED_PACKAGE_WORDS = ("key", "password", "credential", "secret", "token_vault", "vault", "log", "cache")


class RAGError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


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
        reader = PdfReader(str(path))
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


class SafeArchiveValidator:
    def __init__(self, max_files: int = 1000, max_total: int = 536870912, max_ratio: int = 100) -> None:
        self.max_files = max_files
        self.max_total = max_total
        self.max_ratio = max_ratio

    def validate_member(self, info: zipfile.ZipInfo, seen: set[str]) -> None:
        name = info.filename
        path = PurePosixPath(name)
        if name in seen:
            raise RAGError("Archive contains duplicate entries.")
        if path.is_absolute() or ".." in path.parts or PureWindowsPath(name).drive:
            raise RAGError("Archive contains an unsafe path.")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise RAGError("Archive symlinks are not supported.")
        if info.compress_size and info.file_size / max(info.compress_size, 1) > self.max_ratio:
            raise RAGError("Archive compression ratio is suspicious.")
        seen.add(name)

    def extract_validated(self, archive: Path, allowed_files: set[str] | None = None) -> Path:
        staging = Path(tempfile.mkdtemp(prefix="confidencial-archive-"))
        try:
            with zipfile.ZipFile(archive) as zf:
                seen: set[str] = set()
                total = 0
                files = [info for info in zf.infolist() if not info.is_dir()]
                if len(files) > self.max_files:
                    raise RAGError("Archive contains too many files.")
                for info in files:
                    self.validate_member(info, seen)
                    total += info.file_size
                    if total > self.max_total:
                        raise RAGError("Archive uncompressed content is too large.")
                    if allowed_files is not None and info.filename not in allowed_files:
                        raise RAGError("Knowledge-base archive contains an unexpected file.")
                    destination = staging / Path(*PurePosixPath(info.filename).parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(zf.read(info))
            return staging
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise


class SafeZip:
    def __init__(self, max_files: int = 200, max_total: int = 524288000, max_depth: int = 0) -> None:
        self.validator = SafeArchiveValidator(max_files=max_files, max_total=max_total)
        self.max_depth = max_depth

    def expand(self, zip_path: Path) -> tuple[list[Path], Path]:
        staging = self.validator.extract_validated(zip_path)
        paths = [path for path in staging.rglob("*") if path.is_file()]
        for path in paths:
            suffix = path.suffix.lower()
            if suffix == ".zip" and self.max_depth <= 0:
                shutil.rmtree(staging, ignore_errors=True)
                raise RAGError("Nested archives exceed safe depth.")
            if suffix not in SUPPORTED_EXTENSIONS:
                shutil.rmtree(staging, ignore_errors=True)
                raise RAGError("Unsupported file type in ZIP.")
        return paths, staging


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
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                self._model = HashEmbeddingProvider("sha256-hashing-fallback-for-missing-sentence-transformers", self.dimension)
                return
            self._model = SentenceTransformer(self.model_name)
            self.dimension = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        if isinstance(self._model, HashEmbeddingProvider):
            return self._model.embed(texts)
        encoded = self._model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True)
        return [list(map(float, row)) for row in encoded]


class LocalVectorStore:
    def __init__(self) -> None:
        self.vectors: list[list[float]] = []
        self.chunk_ids: list[str] = []

    def clone(self) -> LocalVectorStore:
        cloned = LocalVectorStore()
        cloned.vectors = copy.deepcopy(self.vectors)
        cloned.chunk_ids = list(self.chunk_ids)
        return cloned

    def add(self, chunk_ids: list[str], vectors: list[list[float]]) -> None:
        for vector in vectors:
            if self.vectors and len(vector) != self.dimension():
                raise RAGError("Embedding dimension mismatch.")
        self.chunk_ids.extend(chunk_ids)
        self.vectors.extend([list(map(float, vector)) for vector in vectors])

    def remove_document(self, knowledge_base: KnowledgeBase, document_id: str) -> None:
        keep = [i for i, cid in enumerate(self.chunk_ids) if knowledge_base.chunks[cid].document_id != document_id]
        self.vectors = [self.vectors[i] for i in keep]
        self.chunk_ids = [self.chunk_ids[i] for i in keep]

    def search(self, query: list[float], top_k: int = 5, min_score: float = 0.1) -> list[tuple[str, float]]:
        scores = [(cid, float(sum(a * b for a, b in zip(vector, query)))) for cid, vector in zip(self.chunk_ids, self.vectors)]
        scores.sort(key=lambda item: item[1], reverse=True)
        return [(cid, score) for cid, score in scores[:top_k] if score >= min_score]

    def dimension(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "index.json").write_text(json.dumps({"vectors": self.vectors}), encoding="utf-8")
        metadata = {"chunk_ids": self.chunk_ids, "dimension": self.dimension(), "vector_count": len(self.chunk_ids)}
        (path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> LocalVectorStore:
        store = cls()
        index = json.loads((path / "index.json").read_text(encoding="utf-8"))
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        store.vectors = index["vectors"]
        store.chunk_ids = metadata["chunk_ids"]
        if len(store.vectors) != len(store.chunk_ids):
            raise RAGError("Vector and metadata counts do not match.")
        if store.vectors and metadata.get("dimension") != len(store.vectors[0]):
            raise RAGError("Invalid vector metadata dimension.")
        return store


class PrivacySession:
    def __init__(self, custom_terms: list[str] | None = None) -> None:
        self.custom_terms = sorted([term for term in (custom_terms or []) if term.strip()], key=len, reverse=True)
        self.vault: dict[str, str] = {}
        self._reverse: dict[tuple[str, str], str] = {}
        self._counts: Counter[str] = Counter()
        self._category_next: Counter[str] = Counter()

    @property
    def counts(self) -> dict[str, int]:
        return dict(self._counts)

    def sanitize(self, text: str) -> str:
        sanitized = text
        for term in self.custom_terms:
            sanitized = re.sub(re.escape(term), lambda match: self._token("CUSTOM", match.group(0)), sanitized)
        for category, pattern in PrivacyGateway.PATTERNS.items():
            sanitized = re.sub(pattern, lambda match, cat=category: self._token(cat, match.group(0)), sanitized)
        return sanitized

    def restore(self, text: str) -> str:
        restored = text
        for token, value in sorted(self.vault.items(), key=lambda item: len(item[0]), reverse=True):
            restored = restored.replace(token, value)
        return restored

    def _token(self, category: str, value: str) -> str:
        key = (category, value)
        if key not in self._reverse:
            self._category_next[category] += 1
            token = f"<{category}_{self._category_next[category]:04d}>"
            while token in self.vault:
                self._category_next[category] += 1
                token = f"<{category}_{self._category_next[category]:04d}>"
            self._reverse[key] = token
            self.vault[token] = value
        self._counts[category] += 1
        return self._reverse[key]


class PrivacyGateway:
    PATTERNS = {
        "EMAIL": r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        "PHONE": r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b",
        "IP": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "API_KEY": r"\b(?:sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{24,})\b",
        "UUID": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "URL_SECRET": r"https?://\S*(?:token|key|secret|password)=\S+",
    }

    def create_session(self, custom_terms: list[str] | None = None) -> PrivacySession:
        return PrivacySession(custom_terms)

    def sanitize(self, text: str, custom_terms: list[str] | None = None) -> tuple[str, dict[str, str], dict[str, int]]:
        session = self.create_session(custom_terms)
        sanitized = session.sanitize(text)
        return sanitized, dict(session.vault), session.counts

    def restore(self, text: str, vault: dict[str, str]) -> str:
        for token, value in sorted(vault.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(token, value)
        return text

    def validate_no_leakage(self, payload: str, session: PrivacySession) -> None:
        leaked = [value for value in session.vault.values() if value and value in payload]
        if leaked:
            raise RAGError("Privacy validation failed; external request was blocked.")


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
            excerpt = normalized[:450]
            lines.append(f"- {excerpt} [{citation['number']}]")
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


def save_package(kb: KnowledgeBase, store: LocalVectorStore, path: Path, config: dict[str, Any] | None = None) -> Path:
    package_path = Path(path).with_suffix(".zip")
    tmp = Path(tempfile.mkdtemp(prefix="kbpkg-"))
    try:
        kb.embedding_dimension = store.dimension()
        (tmp / "vectors").mkdir()
        (tmp / "manifest.json").write_text(json.dumps(kb.manifest(), indent=2), encoding="utf-8")
        documents = [document.to_dict() for document in kb.documents.values()]
        (tmp / "documents.json").write_text(json.dumps(documents, indent=2), encoding="utf-8")
        chunk_lines = [json.dumps(chunk.to_dict()) for chunk in kb.chunks.values()]
        (tmp / "chunks.jsonl").write_text("\n".join(chunk_lines) + ("\n" if chunk_lines else ""), encoding="utf-8")
        safe_config = {key: value for key, value in (config or {}).items() if "key" not in key.lower() and "secret" not in key.lower()}
        (tmp / "configuration.json").write_text(json.dumps(safe_config, indent=2), encoding="utf-8")
        (tmp / "README.txt").write_text("Confidencial RAG Version 1 package. Not encrypted.\n", encoding="utf-8")
        store.save(tmp / "vectors")
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(path for path in tmp.rglob("*") if path.is_file()):
                zf.write(file_path, file_path.relative_to(tmp).as_posix())
        return package_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def load_package(path: Path, embedding_provider: EmbeddingProvider | None = None) -> tuple[KnowledgeBase, LocalVectorStore]:
    validator = SafeArchiveValidator()
    staging = validator.extract_validated(Path(path), allowed_files=REQUIRED_PACKAGE_FILES)
    try:
        _reject_prohibited_names(REQUIRED_PACKAGE_FILES)
        manifest = _read_manifest(staging / "manifest.json")
        documents = _read_documents(staging / "documents.json")
        chunks = _read_chunks(staging / "chunks.jsonl", set(documents))
        store = LocalVectorStore.load(staging / "vectors")
        _validate_package_consistency(manifest, documents, chunks, store, embedding_provider)
        kb = KnowledgeBase(
            name=str(manifest["name"]),
            knowledge_base_id=str(manifest["knowledge_base_id"]),
            created_at=str(manifest["created_at"]),
            updated_at=str(manifest["updated_at"]),
            documents=documents,
            chunks=chunks,
            embedding_provider=str(manifest["embedding_provider"]),
            embedding_model=str(manifest["embedding_model"]),
            embedding_dimension=int(manifest["embedding_dimension"]),
        )
        return kb, store
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _reject_prohibited_names(names: set[str]) -> None:
    for name in names:
        lowered = name.lower()
        if any(word in lowered for word in PROHIBITED_PACKAGE_WORDS):
            raise RAGError("Knowledge-base archive contains prohibited files.")


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RAGError("Knowledge-base manifest is malformed.") from exc
    if manifest.get("format") != KB_FORMAT or manifest.get("format_version") != KB_FORMAT_VERSION:
        raise RAGError("Unsupported knowledge-base package.")
    try:
        UUID(str(manifest.get("knowledge_base_id")))
    except ValueError as exc:
        raise RAGError("Knowledge-base package has an invalid identifier.") from exc
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", str(manifest.get("name", ""))):
        raise RAGError("Knowledge-base package has an invalid name.")
    return manifest


def _read_documents(path: Path) -> dict[str, DocumentRecord]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RAGError("Knowledge-base documents registry is malformed.") from exc
    documents: dict[str, DocumentRecord] = {}
    for row in rows:
        document = DocumentRecord(**row)
        if document.document_id in documents:
            raise RAGError("Knowledge-base archive contains duplicate document IDs.")
        documents[document.document_id] = document
    return documents


def _read_chunks(path: Path, document_ids: set[str]) -> dict[str, ChunkRecord]:
    chunks: dict[str, ChunkRecord] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            chunk = ChunkRecord(**json.loads(line))
        except json.JSONDecodeError as exc:
            raise RAGError("Knowledge-base chunk registry is malformed.") from exc
        if chunk.chunk_id in chunks:
            raise RAGError("Knowledge-base archive contains duplicate chunk IDs.")
        if chunk.document_id not in document_ids:
            raise RAGError("Knowledge-base archive contains chunks for missing documents.")
        chunks[chunk.chunk_id] = chunk
    return chunks


def _validate_package_consistency(
    manifest: dict[str, Any],
    documents: dict[str, DocumentRecord],
    chunks: dict[str, ChunkRecord],
    store: LocalVectorStore,
    embedding_provider: EmbeddingProvider | None,
) -> None:
    if int(manifest.get("document_count", -1)) != len(documents):
        raise RAGError("Manifest document count does not match package contents.")
    if int(manifest.get("chunk_count", -1)) != len(chunks):
        raise RAGError("Manifest chunk count does not match package contents.")
    if int(manifest.get("vector_count", -1)) != len(store.chunk_ids):
        raise RAGError("Manifest vector count does not match package contents.")
    if set(store.chunk_ids) != set(chunks):
        raise RAGError("Vector metadata does not match chunk registry.")
    if store.dimension() != int(manifest.get("embedding_dimension", -1)) and store.chunk_ids:
        raise RAGError("Manifest embedding dimension does not match vectors.")
    if embedding_provider is not None:
        if manifest.get("embedding_provider") != embedding_provider.provider_name:
            raise RAGError("Knowledge-base embedding provider is incompatible with this runtime.")
        if manifest.get("embedding_model") != embedding_provider.model_name:
            raise RAGError("Knowledge-base embedding model is incompatible with this runtime.")


def clone_kb(kb: KnowledgeBase) -> KnowledgeBase:
    return copy.deepcopy(kb)


def replacement_chunk(chunk: ChunkRecord, text: str) -> ChunkRecord:
    return replace(chunk, text=text)
