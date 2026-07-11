"""add_documents_engagement_foreign_key

Revision ID: 73688728b480
Revises: 693e23cf7797
Create Date: 2026-07-11 00:00:02.000000

Adds the foreign key deferred in ``eeb31636c877`` (``documents.engagement_id``
had no FK because ``engagements`` wasn't yet represented in this repo's
migration history -- it now is, as of ``12c7b2051fc6``).

ON DELETE is explicitly ``NO ACTION`` (approved decision, Sprint 3
schema-reconciliation review): an engagement with linked documents must
block deletion rather than silently cascading or orphaning those
documents, matching the behavior every other existing foreign key in
this schema already has (``users.organization_id``,
``engagements.organization_id``, ``extracted_text.document_id``,
``ai_analysis_results.document_id`` are all ``NO ACTION``). Declared
explicitly here rather than left as the implicit default so the
intended lifecycle behavior is unambiguous from reading this file.

No column, nullability, or index change -- ``engagement_id`` stays
``NOT NULL`` with its existing ``ix_documents_engagement_id`` index.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '73688728b480'
down_revision: Union[str, None] = '693e23cf7797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        'documents_engagement_id_fkey',
        'documents',
        'engagements',
        ['engagement_id'],
        ['id'],
        ondelete='NO ACTION',
    )


def downgrade() -> None:
    op.drop_constraint('documents_engagement_id_fkey', 'documents', type_='foreignkey')
