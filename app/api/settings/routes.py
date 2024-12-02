# app/api/settings/routes.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ...core.monitoring import capture_error
from ...models.settings import Settings
from ...core.errors import APIError
from ...extensions import db
from marshmallow import ValidationError
from .schemas import SettingSchema, SettingsUpdateSchema

settings_bp = Blueprint("settings", __name__)
setting_schema = SettingSchema()
settings_update_schema = SettingsUpdateSchema()


@settings_bp.route("/tenant/<tenant_id>", methods=["GET"])
@jwt_required()
def get_settings(tenant_id):
    """Get all settings for a tenant"""
    settings = Settings.get_for_owner("tenant", tenant_id)
    if not settings:
        return jsonify({"settings": {}})
    return jsonify({"settings": settings.settings})


@settings_bp.route("/tenant/<tenant_id>", methods=["PUT"])
@jwt_required()
def update_settings(tenant_id):
    """Update multiple settings at once"""
    try:
        data = settings_update_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    settings = Settings.get_for_owner("tenant", tenant_id)
    if not settings:
        settings = Settings(owner_type="tenant", owner_id=tenant_id, settings={})
        db.session.add(settings)

    settings.update_settings(data["settings"])
    db.session.commit()

    return jsonify({"settings": settings.settings})


@settings_bp.route("/tenant/<tenant_id>/<key>", methods=["PUT"])
@capture_error
@jwt_required()
def update_setting(tenant_id, key):
    """Update a single setting"""
    try:
        data = setting_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    settings = Settings.get_for_owner("tenant", tenant_id)
    if not settings:
        settings = Settings(owner_type="tenant", owner_id=tenant_id, settings={})
        db.session.add(settings)

    settings.set_setting(key, data["value"])
    db.session.commit()

    # Return the new value directly
    return jsonify({"key": key, "value": data["value"]})


@settings_bp.route("/tenant/<tenant_id>/<key>", methods=["DELETE"])
@jwt_required()
def delete_setting(tenant_id, key):
    """Delete a specific setting"""
    settings = Settings.get_for_owner("tenant", tenant_id)
    if not settings or key not in settings.settings:
        raise APIError("Setting not found", status_code=404)

    # Create a new dictionary excluding the key we want to delete
    updated_settings = {k: v for k, v in settings.settings.items() if k != key}
    settings.settings = updated_settings
    db.session.add(settings)  # Explicitly mark as modified
    db.session.commit()

    return "", 204
