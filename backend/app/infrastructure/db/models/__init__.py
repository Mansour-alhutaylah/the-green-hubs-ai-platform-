"""ORM models.

Concrete models live in dedicated per-entity modules and are re-exported here
so a single ``from app.infrastructure.db import models`` import (already used
by Alembic's ``env.py``) populates ``Base.metadata`` with every mapped table.
"""

from app.infrastructure.db.models.ai_analysis_result import AIAnalysisResult
from app.infrastructure.db.models.audit_event import AuditEventModel
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.models.engagement import Engagement
from app.infrastructure.db.models.extracted_text import ExtractedText
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User

__all__ = [
    "AIAnalysisResult",
    "AuditEventModel",
    "DocumentModel",
    "Engagement",
    "ExtractedText",
    "Organization",
    "User",
]
