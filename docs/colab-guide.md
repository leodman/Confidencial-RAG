# Colab guide

The launcher clones or fast-forwards the repository, installs extras with `sys.executable`, adds `src` to the active kernel without restart, verifies imports, asks permission for an internet-accessible Gradio share URL, prompts for username and password with `getpass`, and launches authenticated Gradio. No API key is needed for Local only mode and credentials are not persisted.
