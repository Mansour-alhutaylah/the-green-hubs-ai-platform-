"""Shared SQLAlchemy declarative base.

Every future ORM model inherits from ``Base``. This module is also the
anchor point Alembic's ``env.py`` imports for ``target_metadata``.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
