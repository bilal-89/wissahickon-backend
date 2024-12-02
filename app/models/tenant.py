# app/models/tenant.py
from app.extensions import db
from app.core.database import BaseModel
from uuid import uuid4


class Tenant(BaseModel):
    __tablename__ = "tenants"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(100), nullable=False)
    subdomain = db.Column(db.String(100), unique=True, nullable=False)
    settings = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True)

    # Add relationship to UserTenantRole
    user_roles = db.relationship("UserTenantRole", backref="tenant", lazy="dynamic")

    def to_dict(self):
        """Convert tenant to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "subdomain": self.subdomain,
            "settings": self.settings,
            "is_active": self.is_active,
        }
