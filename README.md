# Confidencial RAG

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/leodman/Confidencial-RAG/blob/main/colab/confidencial_rag_launcher.ipynb)

Confidencial RAG Version 1 is an **experimental** local-first retrieval augmented generation application. It supports local document ingestion, local chunking, local embeddings, local vector retrieval, citations, portable knowledge-base ZIP packages, and optional OpenAI-compatible answer generation.

Default mode is **Local only**: no external LLM call is made and no API key is required. External confidential mode sanitizes the question and retrieved chunks before an external request and restores protected placeholders locally. This is not production security and does not guarantee perfect confidentiality.

See `docs/version-1-user-guide.md`, `docs/privacy-gateway.md`, `docs/knowledge-base-format.md`, and `docs/colab-guide.md`.
