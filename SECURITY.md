# Security

Version 1 is an experimental confidential-RAG prototype. Raw confidential values are intended not to be sent to the external LLM when confidential mode is enabled, but regex and user-defined detection can miss values. Knowledge-base archives are not encrypted. Colab runtimes, uploaded files, notebook state, and downloaded archives remain in the user's trust model. Gradio shared URLs are internet-accessible; authentication reduces exposure but is not private infrastructure.
