# app/models/settings.py
from uuid import uuid4
from sqlalchemy.dialects.postgresql import JSON
from ..extensions import db
from ..core.database import BaseModel


class Settings(BaseModel):
    """
    Flexible settings model that can be associated with either a tenant or a user.
    Uses JSON field for maximum flexibility in storing different types of settings.
    """

    __tablename__ = "settings"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_type = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.String(36), nullable=False)
    settings = db.Column(JSON, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, default=True)

    __table_args__ = (db.Index("idx_settings_owner", owner_type, owner_id),)

    def get_setting(self, key, default=None):
        """Get a specific setting value"""
        return self.settings.get(key, default) if self.settings else default

    def set_setting(self, key, value):
        """Set a specific setting value"""
        if self.settings is None:
            self.settings = {}
        self.settings[key] = value
        db.session.add(self)  # Mark as modified

    def update_settings(self, new_settings):
        """Update multiple settings at once"""
        if self.settings is None:
            self.settings = {}
        self.settings.update(new_settings)
        db.session.add(self)  # Mark as modified

    def delete_setting(self, key):
        """Delete a specific setting"""
        if self.settings is not None and key in self.settings:
            del self.settings[key]
            db.session.add(self)  # Mark as modified
            return True
        return False

    @classmethod
    def get_for_owner(cls, owner_type, owner_id):
        """Get settings for a specific owner"""
        return cls.query.filter_by(owner_type=owner_type, owner_id=owner_id, is_active=True).first()
