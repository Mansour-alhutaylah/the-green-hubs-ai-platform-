"""AI / embeddings / vector-store infrastructure.

Placeholder for Sprint 1 -- no AI, RAG, or embedding logic is implemented
yet, and no LangChain dependency is introduced this sprint.

Planned migration (refactored, not copied) from Hemaya's
``backend/vector_store.py`` (OpenAI embeddings + pgvector storage/search)
and ``backend/ai_config.py`` (provider configuration). When implemented,
this package will expose an ``EmbeddingProvider`` interface and a
``VectorRepository`` using parameterized pgvector queries -- Hemaya built
vector literals via string concatenation, which this project will not do.
"""
