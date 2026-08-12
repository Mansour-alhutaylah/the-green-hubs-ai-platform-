"""add_engagements_organization_id_index

Revision ID: a4f1c9d2e7b3
Revises: da0298a9c722
Create Date: 2026-08-09 00:00:00.000000

MVP Slice 3, Organization Data Isolation.

``engagements.organization_id`` is the root of the tenant-ownership chain
for every document-side table: ``documents`` has no ``organization_id``
column of its own, so ``documents``, ``document_chunks`` and
``extracted_text`` all resolve their owner by joining
``documents.engagement_id -> engagements.organization_id``. After this
slice that join is on the hot path of *every* tenant-scoped document read
and write, not just the list endpoint.

Before this migration the only index containing ``organization_id`` on
this table was ``uq_engagements_id_organization_id``, whose leading column
is ``id``. A btree index cannot serve a lookup that does not constrain its
leading column, so every ``WHERE engagements.organization_id = :org``
predicate fell back to a sequential scan of the whole table -- across all
tenants, not just the caller's. That cost is invisible at today's row
counts and grows linearly with the number of engagements every other
organization owns.

The queries this supports, all of which already existed or were added by
this slice:

* ``SQLAlchemyDocumentRepository``'s tenant-scoped select (used by
  ``get_for_organization``, ``get_by_engagement``, ``update_status``,
  ``complete_processing``) and its read-model list/count SQL;
* ``SQLAlchemyEngagementRepository.list``/``count``.

It also gives the ``engagements.organization_id -> organizations.id``
foreign key a supporting index, which PostgreSQL does not create
automatically.

Deliberately minimal: one additive, fully reversible index. No column,
constraint, or data change; nothing else in the schema is touched. A
plain (non-``CONCURRENTLY``) build is correct here because Alembic runs
each migration inside a transaction and the table is small in every
environment this runs against; a future large-table deployment would need
the ``CONCURRENTLY`` variant outside a transaction instead.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a4f1c9d2e7b3'
down_revision: Union[str, None] = 'da0298a9c722'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = 'ix_engagements_organization_id'


def upgrade() -> None:
    op.create_index(INDEX_NAME, 'engagements', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name='engagements')
