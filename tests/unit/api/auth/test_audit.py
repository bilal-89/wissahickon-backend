# tests/unit/core/test_audit.py
import pytest
from app.models.audit_log import AuditLog
from app.extensions import db
from flask import g
from uuid import uuid4


def test_basic_audit_log_creation(app, test_user, test_tenant):
    """Test basic creation of an audit log entry"""
    with app.app_context():
        try:
            # Start a new transaction
            db.session.begin_nested()

            # Create test audit log
            audit_log = AuditLog.log_action(
                action="test_action",
                entity_type="test_entity",
                entity_id=str(uuid4()),
                changes={"field": "value"},
                tenant_id=test_tenant.id,
                user_id=test_user.id,
                ip_address="127.0.0.1",
                user_agent="test-agent",
                endpoint="test-endpoint",
            )

            # Verify the audit log was created
            assert audit_log is not None
            assert audit_log.action == "test_action"
            assert audit_log.entity_type == "test_entity"
            assert audit_log.changes == {"field": "value"}
            assert audit_log.tenant_id == test_tenant.id
            assert audit_log.user_id == test_user.id
            assert audit_log.ip_address == "127.0.0.1"
            assert audit_log.user_agent == "test-agent"
            assert audit_log.endpoint == "test-endpoint"

            # Clean up
            db.session.rollback()
        except Exception as e:
            db.session.rollback()
            raise e
