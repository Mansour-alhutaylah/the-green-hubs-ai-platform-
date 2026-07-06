"""ESG analysis services.

Placeholder for Sprint 1 -- no analysis/RAG logic is implemented yet.

Planned migration (heavy refactor, not a copy) from Hemaya's
``backend/checkpoint_analyzer.py``. That file's *algorithms* are genuinely
strong and worth reusing conceptually: hybrid keyword+BM25 retrieval,
two-pass GPT verification with adaptive re-verification, evidence grounding
via substring/fuzzy matching, multi-signal confidence blending, and
SHA-256-keyed result caching.

Its *structure* is a God object (~1500 lines mixing retrieval, prompting,
caching, scoring, persistence, and progress-reporting, with raw SQL and
hardcoded prompts/thresholds inline) and will not be carried over as-is.
When implemented, this package will split those algorithms into separate,
injectable services, e.g.:

- RetrievalService   -- hybrid keyword/BM25 document retrieval
- VerificationService -- LLM-based claim verification against evidence
- ScoringService      -- confidence blending / compliance scoring
- CacheRepository     -- hash-keyed result caching (infrastructure concern)

each depending only on domain interfaces, per this project's DI rules.
"""
