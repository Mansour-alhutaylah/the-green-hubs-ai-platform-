"""Document ingestion / text-processing infrastructure.

Placeholder for Sprint 1 -- no extraction, chunking, or classification logic
is implemented yet.

Planned migrations from Hemaya:
- ``backend/chunker.py`` -- overlapping text chunker, dependency-free and
  reusable near-verbatim.
- ``backend/text_extractor.py`` -- PDF/DOCX/XLSX/TXT extraction, reusable
  near-verbatim, to be wrapped in an async ``TextExtractor`` interface.
- ``backend/structured_extractor.py`` -- regex-based sentence classifier;
  the classification *approach* is reused, but its compliance-specific
  vocabulary will be replaced with ESG/GRI/SASB terminology.
- ``backend/framework_loader.py`` -- sliding-window GPT-driven extraction
  with dedupe/retry, useful for ingesting ESG framework taxonomies
  (GRI/CSRD/SASB); to be decoupled from Hemaya's Postgres schema.
"""
