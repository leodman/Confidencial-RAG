# Confidencial RAG System Overview

## 1. Objective

Confidencial RAG is a modular Retrieval-Augmented Generation system for persistent document knowledge bases running on temporary compute such as Google Colab.

Its principal security objective is to prevent confidential values from being disclosed to an external LLM. The system retrieves relevant local document context, detects sensitive information, replaces it with reversible local tokens, sends only the sanitized question and context externally, and restores protected values in the returned answer inside the trusted environment.

This is a design objective, not yet a security certification. No external-LLM path should be described as confidential until leakage tests demonstrate that the complete outbound payload is sanitized.

## 2. Operating model

Google Colab provides temporary compute. The knowledge base is persistent and must be saved to and restored from storage outside the Colab runtime.

A normal session follows this lifecycle:

```text
OFF
  -> STARTING
  -> EMPTY or LOADING
  -> READY
  -> INDEXING and/or CHATTING
  -> SAVING
  -> SHUTTING_DOWN
  -> OFF
```

The browser interface is served by Python running in Colab. Because a tunneled web address may be internet-accessible, the web interface is part of the attack surface and requires authentication, session controls, safe errors, and restricted file handling.

## 3. Trust zones

### Trusted processing zone

- active Colab Python runtime;
- document parsers and chunkers;
- metadata and vector stores;
- privacy detector and reversible token vault;
- local embedding and local LLM components;
- restoration logic;
- encrypted persistent storage under user control.

### Untrusted or external zone

- external LLM providers;
- public GitHub repository and its history;
- public issue, PR, action, and artifact content;
- unauthenticated web clients;
- any storage destination that has not been explicitly trusted.

Only an outbound request approved by the privacy gateway may cross from the trusted zone to an external LLM.

## 4. High-level data flow

```text
Documents
  -> loader
  -> normalized document
  -> metadata registry
  -> chunker
  -> embeddings and vector index
  -> retrieval
  -> local privacy gateway
  -> sanitized external request
  -> external response
  -> local restoration
  -> answer with local source references
```

Original documents, raw chunks, embeddings, metadata, token maps, and restored answers remain within the trusted zone.

## 5. Modular architecture

Each component is replaceable behind an explicit interface:

- lifecycle controller;
- storage provider;
- backup and encryption provider;
- document loader;
- metadata repository;
- chunking strategy;
- embedding provider;
- vector store;
- retrieval strategy and reranker;
- privacy detector;
- token vault and restorer;
- local LLM;
- external LLM provider;
- browser UI;
- audit and experiment recorder.

The UI must call the application controller rather than directly manipulating a database or model.

## 6. Knowledge-base persistence

A knowledge-base export is expected to contain versioned application state such as:

```text
knowledge-base/
├── manifest.json
├── metadata.sqlite
├── vector_store/
├── privacy_vault/
├── configuration/
├── ingestion_registry/
└── audit/
```

Original documents may be included or managed separately according to configuration. Confidential exports must be encrypted. The encryption key must not be stored in the same export.

## 7. Incremental ingestion

Every source document receives a stable document identifier and content hash. The ingestion registry records its source path, version, parser, timestamps, classification, and processing status.

Adding one document must not require rebuilding the complete index. The system must support add, update, delete, selected re-index, and full rebuild operations.

## 8. Metadata and references

Every retrievable chunk should retain, where available:

- knowledge-base identifier;
- document identifier and version;
- safe display title;
- original source reference inside the trusted zone;
- path within an imported tree;
- page, sheet, slide, heading, section, or paragraph;
- extraction and ingestion timestamps;
- parser and chunker versions;
- content hash and parent-child relationships.

Answers should cite these local references without exposing confidential filenames externally.

## 9. Experimental behavior

Configuration profiles allow controlled comparison of chunkers, embedding models, vector stores, retrieval methods, privacy detectors, local models, and external providers.

Experiments may record counts, latency, retrieval scores, token counts, detector categories, restoration failures, and synthetic evaluation results. Raw confidential text is excluded from persistent experiment logs by default.

## 10. Initial milestones

1. Lifecycle controller, safe configuration, portable save/load, and web shell.
2. Incremental ingestion for core document types with metadata and citations.
3. Baseline local embeddings, vector retrieval, and synthetic evaluation.
4. Privacy detector, reversible token vault, restoration, and leakage tests.
5. External LLM adapter enabled only through the privacy gateway.
6. Local-only answer mode and configurable experiment profiles.
