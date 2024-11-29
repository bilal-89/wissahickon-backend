# app/core/audit.py
from functools import wraps
from flask import request, g, current_app
from typing import Optional, Dict, Any, Callable
from app.models.audit_log import AuditLog
from app.core.security import get_current_user_id
import json


def track_changes(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Track changes between two dictionaries"""
    changes = {}

    # Find modified fields
    for key in set(before.keys()) | set(after.keys()):
        if key not in before:
            changes[key] = {'added': after[key]}
        elif key not in after:
            changes[key] = {'removed': before[key]}
        elif before[key] != after[key]:
            changes[key] = {
                'from': before[key],
                'to': after[key]
            }

    return changes if changes else None


def audit_action(
        action: str,
        entity_type: str,
        get_entity_id: Optional[Callable] = None
):
    """
    Decorator to audit API actions.

    Args:
        action: Type of action (create, update, delete, etc.)
        entity_type: Type of entity being acted upon
        get_entity_id: Optional function to extract entity ID from response
    """

    def decorator(f: Callable):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get request context
            tenant_id = getattr(g, 'tenant_id', None)
            user_id = get_current_user_id()

            # Execute the original function
            response = f(*args, **kwargs)

            try:
                # Get entity ID if provided
                entity_id = get_entity_id(response) if get_entity_id else None

                # Create audit log
                AuditLog.log_action(
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    changes=request.get_json() if request.is_json else None,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                    endpoint=request.endpoint,
                    metadata={
                        'method': request.method,
                        'path': request.path,
                        'args': dict(request.args),
                        'status_code': getattr(response, 'status_code', None)
                    }
                )
            except Exception as e:
                # Log error but don't disrupt the request
                current_app.logger.error(f"Error creating audit log: {str(e)}")

            return response

        return decorated_function

    return decorator


def audit_model_changes(model_class):
    """
    Decorator to audit model changes.

    Args:
        model_class: SQLAlchemy model class to audit
    """

    def decorator(f: Callable):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get object state before changes
            if 'id' in kwargs:
                before_obj = model_class.query.get(kwargs['id'])
                before_state = before_obj.to_dict() if before_obj else None
            else:
                before_state = None

            # Execute the original function
            result = f(*args, **kwargs)

            try:
                # Get object state after changes
                if isinstance(result, model_class):
                    after_state = result.to_dict()
                    entity_id = str(result.id)

                    # Calculate changes
                    changes = track_changes(before_state, after_state) if before_state else None

                    # Create audit log
                    AuditLog.log_action(
                        action='update' if before_state else 'create',
                        entity_type=model_class.__name__.lower(),
                        entity_id=entity_id,
                        changes=changes,
                        tenant_id=getattr(g, 'tenant_id', None),
                        user_id=get_current_user_id(),
                        metadata={
                            'model': model_class.__name__,
                            'operation': 'update' if before_state else 'create'
                        }
                    )
            except Exception as e:
                # Log error but don't disrupt the operation
                current_app.logger.error(f"Error auditing model changes: {str(e)}")

            return result

        return decorated_function

    return decorator