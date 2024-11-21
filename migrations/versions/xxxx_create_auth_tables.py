# migrations/versions/xxxx_create_auth_tables.py
from alembic import op
import sqlalchemy as sa
from datetime import datetime

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

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('description', sa.String(255)),
        sa.Column('permissions', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('first_name', sa.String(100)),
        sa.Column('last_name', sa.String(100)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('google_id', sa.String(255), unique=True),
        sa.Column('last_login', sa.DateTime()),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id')),
        sa.Column('role_id', sa.String(36), sa.ForeignKey('roles.id')),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    )

    # Create indexes
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_google_id', 'users', ['google_id'])
    op.create_index('idx_tenants_subdomain', 'tenants', ['subdomain'])

def downgrade():
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('tenants')