# app/core/database.py

from ..extensions import db
from datetime import datetime
from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session

@contextmanager
def session_manager() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Ensures proper session handling and cleanup.
    """
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        db.session.remove()

class BaseModel(db.Model):
    __abstract__ = True

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_by_id(cls, id):
        """Safely get instance by ID using the new pattern"""
        return db.session.get(cls, id)

    def save(self):
        """Save instance with proper error handling"""
        with session_manager() as session:
            session.add(self)
            return self

    def delete(self):
        """Delete instance with proper error handling"""
        with session_manager() as session:
            session.delete(self)

    @classmethod
    def create(cls, **kwargs):
        """Create new instance with proper session management"""
        instance = cls(**kwargs)
        return instance.save()