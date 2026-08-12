"""add_document_evidence_review_state

Revision ID: b7d41e0c9a52
Revises: a4f1c9d2e7b3
Create Date: 2026-08-12 10:45:12.108327

MVP Slice 4 (Evidence Review Lifecycle), FND-KC-05's state half.

Adds the current-state evidence decision to ``documents``: which state
the document is in, who decided, when, why, and -- for a supersession --
which document replaced it. Purely additive; no existing column is
altered and no existing row is rewritten beyond receiving the new
columns' defaults.

**Every pre-existing document becomes PENDING_REVIEW, and therefore
retrieval-ineligible.** That is the deliberate, fail-closed choice, not
an oversight: the platform has never had a human evidence approval, so
there is no basis on which any existing row could be backfilled as
VERIFIED. Backfilling approval would be fabricating the exact record
this slice exists to create. Documents already embedded stay embedded
and stay searchable *as data*; they simply stop being returned by
retrieval until a reviewer approves them (see
``SQLAlchemyDocumentChunkEmbeddingRepository.search``).

Column choices:

``evidence_status`` is ``varchar NOT NULL DEFAULT 'PENDING_REVIEW'`` with
a CHECK restricting it to the five canonical spellings. The default is
what makes "a newly uploaded document is not approved evidence" true by
construction rather than by the upload service remembering to set it --
a row inserted by a future code path, a fixture, or direct SQL is
unapproved unless it says otherwise. The CHECK is what lets
``parse_evidence_status`` treat an unrecognized value as a real
integrity fault instead of a formatting variation.

``reviewed_by`` references ``users(id)`` with ``ON DELETE NO ACTION``,
matching every other foreign key in this schema. It is nullable because
``PENDING_REVIEW`` has no reviewer -- and only because of that: the
status-consistency CHECK below requires it to be present in every
decided state.

``review_reason`` is ``text`` rather than a bounded ``varchar``: the
1000-character limit is application policy
(``MAX_REVIEW_REASON_CHARS``), and encoding it as a column type would
mean a policy change needs a table rewrite. The CHECK enforces the same
bound plus a non-blank rule, so a whitespace-only reason cannot be
stored even by a caller that bypasses the service layer entirely.

``superseded_by_document_id`` references ``documents(id)``, also
``NO ACTION``. A self-reference is blocked by CHECK. The successor's
*organization* cannot be constrained declaratively here -- ``documents``
carries no ``organization_id`` column, ownership being the
``engagement_id -> engagements.organization_id`` join -- so that check
lives in the same tenant-scoped SQL predicate that performs the
transition (see ``SQLAlchemyDocumentRepository.transition_evidence``),
never in an after-the-fact application comparison.

Three CHECK constraints, each enforcing an invariant the service layer
also enforces, so a bad partial state cannot be written by any caller:

1. ``ck_documents_evidence_status`` -- the value is one of the five.
2. ``ck_documents_evidence_review_consistency`` -- PENDING_REVIEW carries
   no reviewer, timestamp, reason or successor; VERIFIED carries a
   reviewer and timestamp (its note is optional) and no successor;
   REJECTED and RESTRICTED carry a reviewer, timestamp and reason and no
   successor; SUPERSEDED carries a reviewer, timestamp and reason and
   *may* carry a successor.
3. ``ck_documents_review_reason_format`` -- a stored reason is non-blank
   and within the bound.

Plus ``ck_documents_not_superseded_by_self``.

One index, ``ix_documents_evidence_status``: the review queue
(``GET /documents?evidence_status=PENDING_REVIEW``) filters on it across
an organization's documents. The retrieval join needs no index of its
own -- it reaches ``documents`` by primary key from
``document_chunk_embeddings.document_id`` and applies the state as a
filter on that single row.

Downgrade drops the four constraints, the index and the five columns,
which discards every recorded evidence decision -- unavoidable, since
the decisions have nowhere else to live in the earlier schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d41e0c9a52'
down_revision: Union[str, None] = 'a4f1c9d2e7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors app.domain.evidence.lifecycle. Restated as literals here on
# purpose: a migration is a historical record of what the schema became
# at this revision, and must not silently change meaning later because an
# application constant was edited.
EVIDENCE_STATUSES = ('PENDING_REVIEW', 'VERIFIED', 'REJECTED', 'RESTRICTED', 'SUPERSEDED')
INITIAL_EVIDENCE_STATUS = 'PENDING_REVIEW'
MAX_REVIEW_REASON_CHARS = 1000

_STATUS_LIST = ', '.join(f"'{status}'" for status in EVIDENCE_STATUSES)

_REVIEW_CONSISTENCY = """
(
  evidence_status = 'PENDING_REVIEW'
  AND reviewed_by IS NULL AND reviewed_at IS NULL
  AND review_reason IS NULL AND superseded_by_document_id IS NULL
) OR (
  evidence_status = 'VERIFIED'
  AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
  AND superseded_by_document_id IS NULL
) OR (
  evidence_status IN ('REJECTED', 'RESTRICTED')
  AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
  AND review_reason IS NOT NULL AND superseded_by_document_id IS NULL
) OR (
  evidence_status = 'SUPERSEDED'
  AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
  AND review_reason IS NOT NULL
)
"""

_REASON_FORMAT = f"""
review_reason IS NULL
OR (btrim(review_reason) <> '' AND char_length(review_reason) <= {MAX_REVIEW_REASON_CHARS})
"""


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column(
            'evidence_status',
            sa.String(),
            server_default=INITIAL_EVIDENCE_STATUS,
            nullable=False,
        ),
    )
    op.add_column(
        'documents', sa.Column('reviewed_by', sa.UUID(), nullable=True)
    )
    op.add_column(
        'documents', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('documents', sa.Column('review_reason', sa.Text(), nullable=True))
    op.add_column(
        'documents', sa.Column('superseded_by_document_id', sa.UUID(), nullable=True)
    )

    op.create_foreign_key(
        'fk_documents_reviewed_by_users',
        'documents',
        'users',
        ['reviewed_by'],
        ['id'],
        ondelete='NO ACTION',
    )
    op.create_foreign_key(
        'fk_documents_superseded_by_document',
        'documents',
        'documents',
        ['superseded_by_document_id'],
        ['id'],
        ondelete='NO ACTION',
    )

    op.create_check_constraint(
        'ck_documents_evidence_status', 'documents', f'evidence_status IN ({_STATUS_LIST})'
    )
    op.create_check_constraint(
        'ck_documents_evidence_review_consistency', 'documents', _REVIEW_CONSISTENCY
    )
    op.create_check_constraint(
        'ck_documents_review_reason_format', 'documents', _REASON_FORMAT
    )
    op.create_check_constraint(
        'ck_documents_not_superseded_by_self',
        'documents',
        'superseded_by_document_id IS NULL OR superseded_by_document_id <> id',
    )

    op.create_index('ix_documents_evidence_status', 'documents', ['evidence_status'])


def downgrade() -> None:
    op.drop_index('ix_documents_evidence_status', table_name='documents')
    op.drop_constraint('ck_documents_not_superseded_by_self', 'documents', type_='check')
    op.drop_constraint('ck_documents_review_reason_format', 'documents', type_='check')
    op.drop_constraint(
        'ck_documents_evidence_review_consistency', 'documents', type_='check'
    )
    op.drop_constraint('ck_documents_evidence_status', 'documents', type_='check')
    op.drop_constraint('fk_documents_superseded_by_document', 'documents', type_='foreignkey')
    op.drop_constraint('fk_documents_reviewed_by_users', 'documents', type_='foreignkey')
    op.drop_column('documents', 'superseded_by_document_id')
    op.drop_column('documents', 'review_reason')
    op.drop_column('documents', 'reviewed_at')
    op.drop_column('documents', 'reviewed_by')
    op.drop_column('documents', 'evidence_status')
