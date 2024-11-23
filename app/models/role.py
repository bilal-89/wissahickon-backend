# app/models/role.py
from app.extensions import db
from app.core.database import BaseModel
from uuid import uuid4


class Role(BaseModel):
    __tablename__ = 'roles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON)
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'))
    tenant = db.relationship('Tenant', foreign_keys=[tenant_id])

    # Add relationship to UserTenantRole
    user_tenants = db.relationship('UserTenantRole', backref='role', lazy='dynamic')
