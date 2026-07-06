"""Document ingestion / text-processing infrastructure.

``text_extractor.py`` -- migrated from Hemaya's ``backend/text_extractor.py``
in Sprint 2.3. PDF/DOCX/XLSX/XLS/TXT extraction behind a single async
``extract_text(file_path)`` function. Framework-agnostic: no FastAPI,
SQLAlchemy, or AI/RAG imports.

Still planned:
- ``backend/chunker.py`` -- overlapping text chunker, dependency-free and
  reusable near-verbatim.
- ``backend/structured_extractor.py`` -- regex-based sentence classifier;
  the classification *approach* is reused, but its compliance-specific
  vocabulary will be replaced with ESG/GRI/SASB terminology.
- ``backend/framework_loader.py`` -- sliding-window GPT-driven extraction
  with dedupe/retry, useful for ingesting ESG framework taxonomies
  (GRI/CSRD/SASB); to be decoupled from Hemaya's Postgres schema.
"""
