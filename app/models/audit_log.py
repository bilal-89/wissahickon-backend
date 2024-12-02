# app/models/audit_log.py
from app.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any
import uuid


class AuditLog(db.Model):
    """Model for tracking all auditable actions in the system"""

    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True)
    tenant_id = db.Column(
        db.String(36), db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # What happened
    action = db.Column(db.String(50), nullable=False)  # e.g., 'create', 'update', 'delete'
    entity_type = db.Column(db.String(50), nullable=False)  # e.g., 'user', 'tenant', 'booking'
    entity_id = db.Column(db.String(36), nullable=True)

    # Change details
    changes = db.Column(JSONB, nullable=True)  # Store the actual changes made
    event_metadata = db.Column(
        JSONB, nullable=True
    )  # Additional context about the action (renamed from metadata)

    # Request context
    ip_address = db.Column(db.String(45), nullable=True)  # Support IPv6
    user_agent = db.Column(db.String(255), nullable=True)
    endpoint = db.Column(db.String(255), nullable=True)

    # When it happened
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship("Tenant", backref=db.backref("audit_logs", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("audit_logs", lazy="dynamic"))

    def __repr__(self):
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"

    @staticmethod
    def log_action(
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        event_metadata: Optional[Dict[str, Any]] = None,  # renamed parameter
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> "AuditLog":
        """Create a new audit log entry"""
        log_entry = AuditLog(
            id=str(uuid.uuid4()),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            event_metadata=event_metadata,  # renamed field
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint=endpoint,
        )

        db.session.add(log_entry)
        db.session.commit()

        return log_entry

    def to_dict(self) -> Dict[str, Any]:
        """Convert the audit log entry to a dictionary"""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "changes": self.changes,
            "event_metadata": self.event_metadata,  # renamed field
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "endpoint": self.endpoint,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
