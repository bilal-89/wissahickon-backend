"""create auth tables

Revision ID: 1a2b3c4d5e6f  # You can generate a random hex string here
Revises: None  # This is the first migration
Create Date: 2024-11-22
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'  # Same as above
down_revision = None  # This is the first migration
branch_labels = None
depends_on = None

def upgrade():
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('subdomain', sa.String(100), unique=True, nullable=False),
        sa.Column('settings', sa.JSON()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    )

    # Create roles table with tenant_id
    op.create_table(
        'roles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.String(255)),
        sa.Column('permissions', sa.JSON()),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id')),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.UniqueConstraint('name', 'tenant_id', name='uq_role_name_tenant')
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('first_name', sa.String(100)),
        sa.Column('last_name', sa.String(100)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('google_id', sa.String(255)),
        sa.Column('last_login', sa.DateTime()),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id')),
        sa.Column('role_id', sa.String(36), sa.ForeignKey('roles.id')),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.UniqueConstraint('email', 'tenant_id', name='uq_user_email_tenant'),
        sa.UniqueConstraint('google_id', 'tenant_id', name='uq_user_google_tenant')
    )

    # Create indexes
    op.create_index('idx_users_tenant_email', 'users', ['tenant_id', 'email'])
    op.create_index('idx_users_tenant_google', 'users', ['tenant_id', 'google_id'])
    op.create_index('idx_roles_tenant', 'roles', ['tenant_id'])
    op.create_index('idx_tenants_subdomain', 'tenants', ['subdomain'])

def downgrade():
    # Drop tables in reverse order
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('tenants')