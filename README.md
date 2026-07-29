# Confidencial RAG

A modular confidential RAG system that sanitizes sensitive information before using an external LLM and restores it locally in the final response.

> **Status:** Architecture and project skeleton under development.

## Purpose

Confidencial RAG is an experimental Retrieval-Augmented Generation platform designed to run in Google Colab and expose its controls and chat interface through a Python web application. It maintains a persistent, portable knowledge base while treating every Colab runtime as temporary.

The distinguishing component is a local confidentiality gateway. Retrieved context and user questions are inspected locally, sensitive values are replaced with reversible tokens, and only sanitized material may be sent to an external LLM. The returned answer is restored locally before it is shown to the user.

## Initial goals

- Upload individual documents or a ZIP containing a document tree.
- Support PDF, Microsoft Office, Markdown, QMD, HTML, JSON, YAML, XML, and text formats incrementally.
- Preserve document, page, section, path, version, and ingestion metadata.
- Add, update, remove, and re-index documents without rebuilding the entire knowledge base.
- Save and restore knowledge bases between temporary Colab sessions.
- Provide a browser-based control panel and document chat interface.
- Keep loaders, chunkers, embeddings, vector stores, retrieval, privacy, LLM, storage, and UI components replaceable.
- Make experiments observable without writing confidential text to logs.

## Security boundary

This repository is public and contains source code, documentation, configuration templates, tests, and synthetic examples only.

Never commit:

- API keys, passwords, tokens, certificates, or encryption keys
- original or processed confidential documents
- vector databases, embeddings, metadata databases, or token vaults
- knowledge-base exports, backups, runtime caches, or logs
- notebook outputs containing confidential text

See [SECURITY.md](SECURITY.md) and [docs/system-overview.md](docs/system-overview.md).

## Planned repository layout

```text
Confidencial-RAG/
├── colab/                 # Thin Colab launcher
├── config/                # Safe configuration templates
├── docs/                  # Architecture and operating documentation
├── examples/              # Synthetic, non-confidential examples
├── src/confidencial_rag/  # Application modules
├── tests/                 # Unit and integration tests
├── .gitignore
├── pyproject.toml
└── README.md
```

## Development approach

The first milestone will establish lifecycle management, portable storage, document ingestion, metadata, retrieval, citations, and the browser interface. The privacy gateway will then be introduced behind explicit interfaces and validated with leakage tests before any external-LLM path is considered confidential.

The project name uses the repository spelling **Confidencial RAG**. In English documentation, the intended meaning is **Confidential RAG**.
