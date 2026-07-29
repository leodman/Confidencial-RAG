# Security Policy

## Public repository assumption

Treat every committed file, branch, pull request, issue, action log, and artifact in this repository as public. Git history is not a secure deletion mechanism.

## Prohibited repository content

Do not commit or upload:

- confidential, personal, regulated, or customer documents;
- API keys, passwords, access tokens, certificates, encryption keys, or recovery codes;
- original filenames or metadata that reveal confidential activity;
- vector stores, embeddings, metadata databases, token maps, or privacy vaults;
- exported knowledge bases, backups, caches, logs, debug traces, or notebook outputs containing real data.

Use synthetic fixtures for development and testing.

## Runtime secrets

Secrets must be entered at runtime using hidden input or an approved secret store. They must be held only in process memory where practical, never printed, never included in exceptions, and cleared during shutdown.

## Trust boundary

The Colab runtime, connected storage, browser session, and local privacy components form the confidential processing environment. External LLM providers are outside that boundary. Only content that has passed the privacy policy and leakage checks may cross it.

A Colab-hosted web page is not inherently local. Shared or tunneled URLs must be authenticated and considered internet-accessible.

## Logging

Default logs may include identifiers, counts, timings, hashes, status, and error codes. They must not include raw document text, original user questions, restored answers, confidential filenames, token maps, or secrets.

## Backups

Knowledge-base exports containing confidential data must be encrypted before leaving the active runtime. Encryption keys must be stored separately from encrypted backups.

## Reporting vulnerabilities

Do not disclose a vulnerability with real confidential data in a public issue. Use a private communication channel with the repository owner.
