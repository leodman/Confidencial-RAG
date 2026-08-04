# System overview

Dependency direction is Colab notebook → Gradio UI → `ApplicationController` → service interfaces/concrete local services. The UI delegates ingestion, indexing, retrieval, privacy, LLM, and package operations to the controller.
