# app/models/role.py
from app.extensions import db
from app.core.database import BaseModel
from app.core.constants import Permission  # Add this import
from uuid import uuid4


class Role(BaseModel):
    __tablename__ = "roles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON)
    tenant_id = db.Column(db.String(36), db.ForeignKey("tenants.id"))
    tenant = db.relationship("Tenant", foreign_keys=[tenant_id])
    user_tenants = db.relationship("UserTenantRole", backref="role", lazy="dynamic")

    def __repr__(self):
        return f"<Role {self.name} for tenant {self.tenant_id}>"

    def has_permission(self, permission):
        """Check if role has specific permission"""
        if not self.permissions:
            return False

        # Admin role has all permissions
        if self.permissions.get("admin", False):
            return True

        # Handle both enum and string inputs
        perm_value = permission.value if isinstance(permission, Permission) else str(permission)
        return self.permissions.get(perm_value, False)

    def add_permission(self, permission):
        """Add a permission to the role"""
        if not self.permissions:
            self.permissions = {}

        perm_value = permission.value if isinstance(permission, Permission) else str(permission)
        self.permissions[perm_value] = True
        db.session.commit()

    def remove_permission(self, permission):
        """Remove a permission from the role"""
        if not self.permissions:
            return

        perm_value = permission.value if isinstance(permission, Permission) else str(permission)
        self.permissions.pop(perm_value, None)
        db.session.commit()

    def update_permissions(self, permissions_dict):
        """Update role permissions with a new dictionary"""
        self.permissions = permissions_dict
        db.session.commit()

    def get_permissions(self):
        """Get list of all permissions"""
        return list(self.permissions.keys()) if self.permissions else []

    def to_dict(self):
        """Convert role to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def create_default_roles(tenant_id):
        """Create default roles for a new tenant"""
        roles = [
            {
                "name": "admin",
                "permissions": {"admin": True},
                "description": "Full access to all features",
            },
            {
                "name": "staff",
                "permissions": {
                    Permission.VIEW_USERS.value: True,
                    Permission.USE_FEATURE_X.value: True,
                    Permission.USE_FEATURE_Y.value: True,
                },
                "description": "Standard staff access",
            },
            {
                "name": "user",
                "permissions": {Permission.USE_FEATURE_X.value: True},
                "description": "Basic user access",
            },
        ]

        created_roles = []
        for role_data in roles:
            role = Role(tenant_id=tenant_id, **role_data)
            db.session.add(role)
            created_roles.append(role)

        db.session.commit()
        return created_roles

    @staticmethod
    def get_role_by_name(tenant_id, role_name):
        """Get a role by name within a tenant"""
        return Role.query.filter_by(tenant_id=tenant_id, name=role_name).first()

    @classmethod
    def get_or_create_default_role(cls, tenant_id, role_name="user"):
        """Get or create a default role for a tenant"""
        role = cls.get_role_by_name(tenant_id, role_name)
        if not role:
            role = Role(
                tenant_id=tenant_id,
                name=role_name,
                description=f"Default {role_name} role",
                permissions={Permission.USE_FEATURE_X.value: True},
            )
            db.session.add(role)
            db.session.commit()
        return role
