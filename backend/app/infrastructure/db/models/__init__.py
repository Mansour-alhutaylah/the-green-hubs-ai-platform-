"""ORM models.

Concrete models live in dedicated per-entity modules and are re-exported here
so a single ``from app.infrastructure.db import models`` import (already used
by Alembic's ``env.py``) populates ``Base.metadata`` with every mapped table.
"""

from app.infrastructure.db.models.document import DocumentModel

__all__ = ["DocumentModel"]
