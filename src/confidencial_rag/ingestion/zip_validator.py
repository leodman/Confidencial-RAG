from __future__ import annotations

import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from confidencial_rag.ingestion.base import RAGError, SUPPORTED_EXTENSIONS


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
        if stat.S_ISLNK(info.external_attr >> 16):
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


__all__ = ["SafeArchiveValidator", "SafeZip"]
