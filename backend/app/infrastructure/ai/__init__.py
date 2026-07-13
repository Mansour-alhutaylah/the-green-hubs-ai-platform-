"""AI / embeddings / vector-store infrastructure.

Sprint 3.6A, Vector Retrieval Foundation: ``OpenAIEmbeddingProvider``
implements ``app.domain.embedding_provider.EmbeddingProvider`` via narrow
``httpx`` calls (mirroring ``SupabaseDocumentStorage``'s existing
narrow-HTTP precedent, not the ``openai`` SDK). Still no RAG, chat, LLM
completion, or LangChain dependency -- vector similarity search itself is
a repository concern
(``SQLAlchemyDocumentChunkEmbeddingRepository.search()``). Every vector
value is passed as a genuine bound query parameter, never interpolated
into SQL text -- the anti-pattern in Hemaya's own
``backend/vector_store.py`` that this project deliberately avoids.
"""
