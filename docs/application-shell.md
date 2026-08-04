# Application Shell

The Gradio shell exposes System, Knowledge Base, Documents, Chat, and Settings areas. UI callbacks call `ApplicationController` methods and display safe summaries: lifecycle state, active knowledge base, embedding provider/model/dimension, document/chunk/vector counts, citations, retrieved evidence, privacy counts, and an optional sanitized preview.

The API key input is password-style and is passed only to the controller call that needs it. It is not returned by callbacks, persisted, or exported.
