# Privacy Gateway

The privacy gateway uses one request-scoped session and one in-memory vault for the outbound external-LLM request. The session sanitizes the question, selected context chunks, and citation labels/filenames; repeated values reuse a token and custom terms are processed longest-match-first.

Version 2 has three replaceable layers: entity detection, a configurable category policy, and the
existing reversible tokenization session. A composite detector combines deterministic regular
expressions for structured values (email, phone, IPv4, SSN-like strings, credit-card-like strings,
API keys, UUIDs, and sensitive URLs) with local semantic NER. Semantic detection uses spaCy and the
lightweight `en_core_web_sm` English model, mapping only spaCy `PERSON` to `PERSON` and `ORG` to
`COMPANY`. Runtime detection makes no network request; the Version 2 Colab setup installs the model
before the application starts.

The default policy protects people, companies, email addresses, phone numbers, and explicitly
identified internal projects. Other spaCy labels, including GPE, LOC, PRODUCT, DATE, and MONEY, are
not selected. PRODUCT and TECHNOLOGY are not confidential by default. A configurable, normalized
public-name allowlist prevents common public technologies—including Azure, Snowflake, AWS, Python,
Linux, Docker, Kubernetes, OpenAI, Microsoft Azure, and Google Cloud—from being masked even when the
NER model labels one as an organization. Business-specific customer names are not allowlisted.

Manual terms remain authoritative and are reported separately from automatic detections. Reports
include automatic occurrence counts by category, the custom occurrence count, and total replacement
occurrences. Manual spans win when they overlap an automatic detection. This remains experimental,
not production-grade DLP: the small statistical model can miss names or classify ambiguous text
incorrectly, and its output can vary when the pinned spaCy/model range is upgraded. Another local
detector can implement the entity-detector interface without changing the gateway API. Failure to
load or run semantic NER blocks confidential external requests rather than silently using partial
detection.

Detected categories include PERSON and COMPANY from local NER, plus email, phone, IPv4, SSN-like strings, credit-card-like strings, API-key-like strings, UUIDs, sensitive URLs, and custom terms. Statistical and regex detection can miss values. The token vault is not logged, displayed, persisted, or sent externally.
