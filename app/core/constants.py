# app/core/constants.py
from enum import Enum


class Permission(Enum):
    # Tenant Management
    MANAGE_TENANT = "manage_tenant"
    VIEW_TENANT = "view_tenant"

    # User Management
    MANAGE_USERS = "manage_users"
    VIEW_USERS = "view_users"

    # Role Management
    MANAGE_ROLES = "manage_roles"
    VIEW_ROLES = "view_roles"

    # Feature Access
    USE_FEATURE_X = "use_feature_x"
    USE_FEATURE_Y = "use_feature_y"
