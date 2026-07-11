"""create_organizations_users_engagements

Revision ID: 12c7b2051fc6
Revises: eeb31636c877
Create Date: 2026-07-11 00:00:00.000000

Retroactively brings ``organizations``, ``users``, and ``engagements``
under Alembic control. These tables already exist in the shared
Supabase database (created out-of-band, before this repo's Alembic
history began) -- this migration's DDL is a hand-authored,
column-for-column mirror of that already-verified live schema (Sprint 3
schema-reconciliation review), not a new design. The shared instance is
reconciled via ``alembic stamp`` rather than by executing this
migration's DDL there; a genuinely fresh database runs this migration
for real.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '12c7b2051fc6'
down_revision: Union[str, None] = 'eeb31636c877'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'organizations',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_table(
        'engagements',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column(
            'status',
            sa.String(length=50),
            server_default=sa.text("'planning'::character varying"),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('engagements')
    op.drop_table('users')
    op.drop_table('organizations')
