# app/api/settings/schemas.py
from marshmallow import Schema, fields, validates, ValidationError


class SettingSchema(Schema):
    """Schema for validating setting values"""

    key = fields.Str(required=True)
    value = fields.Raw(required=True)


class SettingsUpdateSchema(Schema):
    """Schema for bulk settings updates"""

    settings = fields.Dict(keys=fields.Str(), values=fields.Raw(), required=True)
