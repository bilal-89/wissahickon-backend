# app/models/user.py
from app.extensions import db
from app.core.database import BaseModel
from app.core.security import SecurityMixin
from uuid import uuid4
from datetime import datetime


class Tenant(BaseModel):
    __tablename__ = 'tenants'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(100), nullable=False)
    subdomain = db.Column(db.String(100), unique=True, nullable=False)
    settings = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Tenant {self.name}>'


class Role(BaseModel):
    __tablename__ = 'roles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON)

    def __repr__(self):
        return f'<Role {self.name}>'


class User(BaseModel, SecurityMixin):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    google_id = db.Column(db.String(255), unique=True)
    last_login = db.Column(db.DateTime)

    # Multi-tenancy support
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'))
    tenant = db.relationship('Tenant', foreign_keys=[tenant_id], backref=db.backref('users', lazy='dynamic'))

    # Role relationship
    role_id = db.Column(db.String(36), db.ForeignKey('roles.id'))
    role = db.relationship('Role', backref='users')

    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
            'role': self.role.name if self.role else None,
            'tenant_id': self.tenant_id
        }

    def update_last_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()