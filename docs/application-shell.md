# Application-shell architecture

The Gradio layer is a presentation adapter. Its callbacks call the shared
`ApplicationController`, render the returned state, and convert expected controller
errors into user-visible messages. The UI does not read or write manifests itself.

For this milestone, the controller owns a temporary runtime directory and writes only
content-free synthetic JSON manifests. Later storage, document parsing, retrieval,
privacy/tokenization, encryption, and LLM implementations must sit behind controller or
service interfaces; they must not be called directly from Gradio or the Colab notebook.
The notebook remains a bootstrapper that updates the repository, installs the `ui` extra,
and chooses explicit launch settings.

The safe configuration reference remains `config/default.example.yaml`. Runtime secrets
and runtime configuration are intentionally neither generated nor committed.
