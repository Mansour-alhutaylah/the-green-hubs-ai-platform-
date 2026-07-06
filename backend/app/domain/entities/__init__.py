"""Domain entities.

Placeholder for Sprint 1. This package will hold plain, framework-agnostic
Python entities (no SQLAlchemy, no Pydantic) describing the platform's core
concepts once business logic is implemented, for example:

- Document        (an uploaded sustainability report/policy)
- ExtractedMetric  (an ESG metric parsed from a Document)
- Framework        (a sustainability taxonomy/standard, e.g. GRI, CSRD, SASB)
- AuditLog         (a record of who did what, when)

These mirror the *shape* of entities Hemaya modeled in its ``backend/models.py``
(Policy, ComplianceResult, Gap, Framework, AuditLog, ...) as design inspiration
only -- Hemaya's models are SQLAlchemy ORM classes tied directly to routes;
these domain entities must stay independent of any persistence framework.
"""
