# Security Policy

## Core rule

Treat this repository as fully public. Never commit confidential documents, extracted text, embeddings, vector indexes, metadata databases, reversible token mappings, encryption keys, API keys, session logs, backups, or real customer examples.

## Secrets

Secrets must be entered at runtime, preferably with a hidden prompt such as `getpass`, and stored only in process memory or environment variables for the active session. Do not place secrets in notebooks, configuration files, screenshots, issues, pull requests, or logs.

## Data handling

The external LLM is outside the trusted boundary. Only sanitized questions and sanitized retrieved context may be transmitted externally. Original values and reversible mappings must remain inside the confidential runtime.

## Reporting vulnerabilities

Do not open a public issue containing sensitive details. Contact the repository owner privately and provide a minimal reproduction using synthetic data.
