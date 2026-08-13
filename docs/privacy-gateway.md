# Privacy Gateway

The privacy gateway uses one request-scoped session and one in-memory vault for the outbound external-LLM request. The session sanitizes the question, selected context chunks, and citation labels/filenames; repeated values reuse a token and custom terms are processed longest-match-first.

Version 2 adds three replaceable layers: an offline deterministic entity detector, a configurable
category policy, and the existing reversible tokenization session. The initial detector recognizes
structured values (including email, phone, and IPv4) plus conservative PERSON and COMPANY patterns.
It uses no network service and adds no dependency. The default policy protects people, companies,
email addresses, phone numbers, and explicitly supplied internal projects; PRODUCT and TECHNOLOGY
remain visible. Common public technology names are excluded from the named-entity heuristics.

Manual terms remain authoritative and are reported separately from automatic detections. Reports
include automatic occurrence counts by category, the custom occurrence count, and total replacement
occurrences. This deterministic approach is an experimental, precision-oriented baseline—not
production-grade confidentiality—and may miss names or classify ambiguous names incorrectly. A
future local NLP or LLM detector can implement the entity-detector interface without changing the
gateway API.

Detected categories include email, phone, IPv4, SSN-like strings, credit-card-like strings, API-key-like strings, UUIDs, sensitive URLs, and custom terms. Detection is regex/user-input based and can miss values. The token vault is not logged, displayed, persisted, or sent externally.
