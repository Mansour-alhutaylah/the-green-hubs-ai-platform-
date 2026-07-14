"""ESG / sustainability analysis services.

Sprint 3.6B, RAG + Structured Sustainability Analysis Foundation:
``RagAnalysisService`` (``rag_analysis.py``) is the orchestrator --
tenant-safe idempotent claim/retry/reclaim, retrieval via the existing
``VectorRetrievalService``, server-controlled citation source-key
mapping, and structured-output validation. ``request_hash.py``,
``structured_output.py``, and ``prompts.py`` are its supporting,
independently testable pieces.

A heavier refactor inspired by Hemaya's ``checkpoint_analyzer.py``
algorithms (hybrid keyword+BM25 retrieval, two-pass verification,
multi-signal confidence blending) remains a possible future direction,
but is out of scope for this sprint -- see the sprint plan's explicit
"do not implement" list (hybrid keyword search, multi-provider failover,
autonomous agents, human review workflow).
"""
