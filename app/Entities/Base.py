"""
Base — DeclarativeBase parent every entity inherits from.

`Base.metadata` is the master registry of all tables. Alembic reads this
to autogenerate migrations, so every entity must import from here.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass