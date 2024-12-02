"""add user tenant roles junction table

Revision ID: 8c334451b2be  # Your actual revision ID will be different
Revises: 1a2b3c4d5e6f
Create Date: 2024-11-22
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic
revision = '8c334451b2be'  # Your actual revision ID will be different
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None

def upgrade():
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create user_tenant_roles table
    op.create_table(
        'user_tenant_roles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('role_id', sa.String(36), sa.ForeignKey('roles.id'), nullable=False),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.UniqueConstraint('user_id', 'tenant_id', name='uq_user_tenant_role')
    )

    # Create indexes
    op.create_index('idx_user_tenant_roles_user', 'user_tenant_roles', ['user_id'])
    op.create_index('idx_user_tenant_roles_tenant', 'user_tenant_roles', ['tenant_id'])
    op.create_index('idx_user_tenant_roles_role', 'user_tenant_roles', ['role_id'])

    # Migrate existing data
    op.execute("""
        INSERT INTO user_tenant_roles (
            id, 
            user_id, 
            tenant_id, 
            role_id, 
            is_primary,
            is_active, 
            created_at, 
            updated_at
        )
        SELECT 
            uuid_generate_v4()::varchar,
            id,
            tenant_id,
            role_id,
            TRUE,
            is_active,
            created_at,
            updated_at
        FROM users
        WHERE tenant_id IS NOT NULL AND role_id IS NOT NULL
    """)

    # Make the columns nullable since they'll be managed through the junction table
    op.alter_column('users', 'tenant_id',
        existing_type=sa.String(36),
        nullable=True
    )
    op.alter_column('users', 'role_id',
        existing_type=sa.String(36),
        nullable=True
    )

def downgrade():
    # Make columns non-nullable again
    op.alter_column('users', 'tenant_id',
        existing_type=sa.String(36),
        nullable=False
    )
    op.alter_column('users', 'role_id',
        existing_type=sa.String(36),
        nullable=False
    )

    # Drop the junction table
    op.drop_table('user_tenant_roles')

    # We don't remove the UUID extension as other parts of the system might use it