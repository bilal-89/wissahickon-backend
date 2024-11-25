# app/models/user_tenant_role.py
from app.extensions import db
from app.core.database import BaseModel
from uuid import uuid4


class UserTenantRole(BaseModel):
    __tablename__ = 'user_tenant_roles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    role_id = db.Column(db.String(36), db.ForeignKey('roles.id'), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)