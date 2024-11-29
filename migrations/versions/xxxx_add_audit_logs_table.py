"""add audit logs table

Revision ID: [you'll get this from running flask db revision]
Revises: [your previous revision]
Create Date: [current timestamp]

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = ''  # you'll get this from running flask db revision
down_revision = ''  # your previous revision id
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('changes', postgresql.JSONB, nullable=True),
        sa.Column('event_metadata', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('timestamp', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # Create indexes
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_entity_type', 'audit_logs', ['entity_type'])

def downgrade():
    op.drop_index('ix_audit_logs_entity_type')
    op.drop_index('ix_audit_logs_action')
    op.drop_index('ix_audit_logs_timestamp')
    op.drop_index('ix_audit_logs_user_id')
    op.drop_index('ix_audit_logs_tenant_id')
    op.drop_table('audit_logs')