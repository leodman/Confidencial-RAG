# System Overview

Confidencial RAG Version 1 follows a local-first dependency direction:

```text
Colab notebook → Gradio UI → ApplicationController → service interfaces → concrete local implementations
```

The controller coordinates ingestion, chunking, local embeddings, vector search, privacy tokenization, answer generation, and knowledge-base import/export. The UI and notebook do not parse documents, embed text, query vectors, call LLMs, sanitize content, or inspect archive internals directly.

Version 1 supports local-only extractive answers by default and optional OpenAI-compatible generation. In confidential external mode, the external provider receives only sanitized question, selected context, and sanitized citation labels. This is experimental and does not guarantee complete confidentiality.
