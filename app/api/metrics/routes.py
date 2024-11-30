# app/api/metrics/routes.py
from flask import Blueprint, jsonify
from app.core.metrics import get_current_metrics
from flask_jwt_extended import jwt_required
from app.core.middleware import TenantMiddleware

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/metrics')
@jwt_required()
@TenantMiddleware.tenant_required
def get_metrics():
    """Get application metrics"""
    return jsonify(get_current_metrics())