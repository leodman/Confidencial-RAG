# Knowledge-Base Format

Version 1 exports unencrypted ZIP packages containing `manifest.json`, `documents.json`, `chunks.jsonl`, `configuration.json`, `README.txt`, and a `vectors/` directory. The manifest records format/version, UUID, name, timestamps, document/chunk/vector counts, embedding provider, embedding model, and embedding dimension.

Imports are treated as untrusted archives. The importer validates safe paths, expected files, JSON/JSONL structure, UUID/name format, count consistency, chunk/vector alignment, embedding compatibility, and prohibited secret/log/cache filenames before activating the package.
