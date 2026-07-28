from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

# Re-export for convenience
__all__ = ["Base"]


class Base(DeclarativeBase):
    pass
