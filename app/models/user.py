# app/models/user.py
from app.extensions import db
from app.core.database import BaseModel
from app.core.security import SecurityMixin
from uuid import uuid4
from datetime import datetime
from .user_tenant_role import UserTenantRole


class User(BaseModel, SecurityMixin):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    google_id = db.Column(db.String(255))
    last_login = db.Column(db.DateTime)

    # These will now be managed through UserTenantRole but kept for backwards compatibility
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=True)
    role_id = db.Column(db.String(36), db.ForeignKey('roles.id'), nullable=True)

    # Add relationship to UserTenantRole
    tenant_roles = db.relationship('UserTenantRole', backref='user', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('email', 'tenant_id', name='uq_user_email_tenant'),
        db.UniqueConstraint('google_id', 'tenant_id', name='uq_user_google_tenant'),
    )

    def __repr__(self):
        return f'<User {self.email}>'

    def add_tenant_role(self, tenant, role, is_primary=False):
        """Add a role for this user in a specific tenant"""
        # Check for existing role in this tenant - force evaluation with .all()
        existing = self.tenant_roles.filter_by(tenant_id=tenant.id).all()
        if existing:
            raise ValueError(f"User already has a role in tenant: {tenant.name}")

        # If this is going to be primary, remove any existing primary
        if is_primary:
            current_primary = self.tenant_roles.filter_by(is_primary=True).first()
            if current_primary:
                current_primary.is_primary = False
                db.session.add(current_primary)

        # Create new tenant role relationship
        tenant_role = UserTenantRole(
            user_id=self.id,
            tenant_id=tenant.id,
            role_id=role.id,
            is_primary=is_primary
        )

        db.session.add(tenant_role)
        db.session.commit()

        return tenant_role

    def get_tenant_roles(self):
        """Get list of all tenant roles"""
        return self.tenant_roles.all()

    def get_role_for_tenant(self, tenant):
        """Get the user's role in a specific tenant"""
        tenant_role = self.tenant_roles.filter_by(tenant_id=tenant.id).first()
        return tenant_role.role if tenant_role else None

    @property
    def primary_tenant_role(self):
        """Get the user's primary tenant role relationship"""
        return self.tenant_roles.filter_by(is_primary=True).first()

    @property
    def primary_tenant(self):
        """Get the user's primary tenant"""
        primary = self.primary_tenant_role
        return primary.tenant if primary else None

    @property
    def primary_role(self):
        """Get the user's primary role"""
        primary = self.primary_tenant_role
        return primary.role if primary else None

    def to_dict(self):
        """Serialize user to dict with tenant/role information"""
        primary = self.primary_tenant_role
        basic_data = {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
        }

        if primary:
            basic_data['primary_tenant'] = {
                'id': primary.tenant.id,
                'name': primary.tenant.name,
                'role': primary.role.name,
                'subdomain': primary.tenant.subdomain
            }

        basic_data['other_tenants'] = [{
            'id': tr.tenant.id,
            'name': tr.tenant.name,
            'role': tr.role.name,
            'subdomain': tr.tenant.subdomain
        } for tr in self.get_tenant_roles() if not tr.is_primary]

        return basic_data

    def update_last_login(self):
        """Update the last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()

    def switch_primary_tenant(self, tenant):
        """Switch the user's primary tenant"""
        # Find the tenant role
        new_primary = self.tenant_roles.filter_by(tenant_id=tenant.id).first()
        if not new_primary:
            raise ValueError(f"User has no role in tenant: {tenant.name}")

        # Remove current primary
        current_primary = self.tenant_roles.filter_by(is_primary=True).first()
        if current_primary:
            current_primary.is_primary = False
            db.session.add(current_primary)

        # Set new primary
        new_primary.is_primary = True
        db.session.add(new_primary)
        db.session.commit()

        return new_primary