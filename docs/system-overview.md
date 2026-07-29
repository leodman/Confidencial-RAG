# Confidencial RAG: System Overview

## Purpose

Confidencial RAG is a modular retrieval-augmented generation system designed to use confidential document collections while preventing raw sensitive information from being sent to an external large language model.

The system runs as a Python application in Google Colab and exposes a browser-based interface. Colab is treated as an ephemeral execution environment: databases, indexes, vaults, and configuration state must be explicitly loaded at startup and saved before shutdown.

## Core data flow

1. Documents are uploaded individually or as a ZIP preserving a directory tree.
2. Local loaders extract text, structure, and metadata.
3. The indexing pipeline creates chunks, embeddings, document lineage, and source references.
4. A user asks a question through the web interface.
5. The retriever selects relevant chunks locally.
6. The privacy gateway detects confidential entities in both the question and retrieved context.
7. Sensitive values are replaced with stable reversible tokens.
8. Only the sanitized request is sent to the configured external LLM.
9. The response is returned to the confidential runtime.
10. Tokens are restored locally and the answer is shown with document references.

## Trust boundaries

### Trusted confidential runtime

- uploaded documents
- extracted text and metadata
- vector database and embeddings
- local models
- reversible token vault
- original and restored responses

### Public repository

- source code
- documentation
- configuration templates
- synthetic examples and tests

### Untrusted external services

- external LLM providers
- public GitHub content
- public web tunnels

External services must receive only the minimum sanitized information required for the requested operation.

## Application lifecycle

The web interface will provide these primary operations:

- Start system
- Create or load a knowledge base
- Upload documents or ZIP trees
- Index new or changed documents
- Chat with the active knowledge base
- Inspect the exact sanitized payload before transmission
- Save or export the active knowledge base
- Perform a safe shutdown

## Persistent knowledge bases

A knowledge base is a portable directory or encrypted archive containing:

- metadata database
- vector index
- embedding and chunk records
- document registry and lineage
- privacy vault
- configuration snapshot
- non-sensitive operational statistics

Incremental indexing is required. Adding one document must not force a complete rebuild.

## Modular design

Each major capability is replaceable behind a stable interface:

- document loaders
- chunking strategies
- embedding models
- vector stores
- retrieval and reranking
- privacy detectors
- token vaults
- local LLMs
- external LLM providers
- storage backends
- web interface
- evaluation and leakage tests

Configuration profiles will allow the same question and document set to be tested across different implementations.

## Initial milestone

The first working milestone will support:

- PDF, DOCX, Markdown, QMD, HTML, JSON, and plain text
- local metadata storage
- local vector retrieval
- source citations
- save and reload of a knowledge base
- browser chat launched from Colab
- a mock LLM provider for tests

The privacy gateway and external LLM connector will be integrated only after the baseline RAG lifecycle is testable.

## Security principles

- Fail closed: if sanitization cannot be verified, do not send the request externally.
- No secret persistence in GitHub or notebook source.
- No raw document text in normal logs.
- Filenames and metadata are treated as potentially confidential.
- The user can inspect the sanitized outbound payload.
- Backups containing confidential material should be encrypted.
- Synthetic data is used in all public tests and examples.
