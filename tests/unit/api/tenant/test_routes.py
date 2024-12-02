# test_tenant_routes.py
from uuid import uuid4
from app.models.tenant import Tenant
from app.models.role import Role, Permission
from app.models.user_tenant_role import UserTenantRole
from app.extensions import db


class TestTenantRoutes:
    def setup_method(self, method):
        """Setup method that runs before each test"""
        # Clear any existing user-tenant relationships
        db.session.query(UserTenantRole).delete()
        db.session.commit()

    def ensure_user_tenant_role(self, user, tenant, permissions=None):
        """Helper to ensure user has a role in the tenant"""
        # Check for existing role
        user_role = UserTenantRole.query.filter_by(user_id=user.id, tenant_id=tenant.id).first()

        if not user_role:
            # Create a role for the tenant if it doesn't exist
            role = Role.query.filter_by(tenant_id=tenant.id).first()
            if not role:
                role = Role(id=str(uuid4()), name="test_role", tenant_id=tenant.id)
                db.session.add(role)
                db.session.commit()

            # Create the user-tenant-role relationship
            user_role = UserTenantRole(
                id=str(uuid4()),
                user_id=user.id,
                tenant_id=tenant.id,
                role_id=role.id,
                is_primary=True,
            )
            db.session.add(user_role)
            db.session.commit()

        # Set permissions if provided
        if permissions:
            role = user_role.role
            role.permissions = permissions
            db.session.commit()

        return user_role

    def setup_admin_permissions(self, role):
        """Helper to set up admin permissions"""
        role.permissions = {
            "admin": True,
            Permission.VIEW_TENANT.value: True,
            Permission.MANAGE_TENANT.value: True,
            Permission.VIEW_USERS.value: True,
            Permission.MANAGE_ROLES.value: True,
            Permission.VIEW_ROLES.value: True,
        }
        db.session.commit()

    def setup_basic_permissions(self, role):
        """Helper to set up basic permissions"""
        role.permissions = {
            Permission.VIEW_TENANT.value: True,
            Permission.VIEW_USERS.value: True,
            Permission.VIEW_ROLES.value: True,
            Permission.USE_FEATURE_X.value: True,
        }
        db.session.commit()

    def test_list_tenants(self, client, test_user_with_role, test_tenant):
        # Ensure user has role and permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_basic_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        response = client.get("/api/tenants", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "tenants" in data
        assert "primary_tenant" in data
        assert len(data["tenants"]) >= 1
        assert data["primary_tenant"]["id"] == test_tenant.id

    def test_get_tenant_details(self, client, test_user_with_role, test_tenant):
        # Ensure user has role and permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_basic_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        response = client.get(f"/api/tenants/{test_tenant.id}", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == test_tenant.id
        assert data["name"] == test_tenant.name
        assert data["subdomain"] == test_tenant.subdomain

    def test_list_tenant_users(self, client, test_user_with_role, test_tenant):
        # Ensure user has role and permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_basic_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        response = client.get(f"/api/tenants/{test_tenant.id}/users", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "users" in data
        assert len(data["users"]) >= 1
        assert any(user["email"] == test_user_with_role.email for user in data["users"])

    def test_create_tenant(self, client, test_user_with_role, test_tenant):
        # Ensure user has role and admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_admin_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        new_tenant_data = {
            "name": "New Business",
            "subdomain": "new-business",
            "settings": {"theme": "light"},
        }

        response = client.post("/api/tenants", json=new_tenant_data, headers=headers)

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == new_tenant_data["name"]
        assert data["subdomain"] == new_tenant_data["subdomain"]

        # Clean up
        new_tenant = Tenant.query.filter_by(subdomain="new-business").first()
        if new_tenant:
            db.session.query(UserTenantRole).filter_by(tenant_id=new_tenant.id).delete()
            db.session.query(Role).filter_by(tenant_id=new_tenant.id).delete()
            db.session.delete(new_tenant)
            db.session.commit()

    def test_create_tenant_duplicate_subdomain(self, client, test_user_with_role, test_tenant):
        # Ensure user has role and admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_admin_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        response = client.post(
            "/api/tenants",
            json={"name": "Duplicate Business", "subdomain": test_tenant.subdomain},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "Subdomain already in use" in data.get("message", "")

    def test_permission_denied_list_tenants(self, client, test_user_with_role, test_tenant):
        """Test access denied when user lacks VIEW_TENANT permission"""
        # Ensure user has role but explicitly set empty permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        user_role.role.permissions = {}  # Explicitly set empty permissions
        db.session.commit()

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        response = client.get("/api/tenants", headers=headers)
        assert response.status_code == 403  # Should be denied due to missing permission

    def test_list_tenant_roles(self, client, test_user_with_role, test_tenant):
        # Ensure user has role and permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_basic_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        response = client.get(f"/api/tenants/{test_tenant.id}/roles", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "roles" in data
        assert len(data["roles"]) >= 1

    def test_create_tenant_role(self, client, test_user_with_role, test_tenant):
        # Ensure user has role and admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_admin_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        new_role_data = {
            "name": "custom-role",
            "description": "Custom role for testing",
            "permissions": {Permission.VIEW_TENANT.value: True},
        }

        response = client.post(
            f"/api/tenants/{test_tenant.id}/roles", json=new_role_data, headers=headers
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == new_role_data["name"]
        assert data["permissions"] == new_role_data["permissions"]

        # Clean up
        role = Role.query.filter_by(name="custom-role", tenant_id=test_tenant.id).first()
        if role:
            db.session.delete(role)
            db.session.commit()

    def test_permission_denied_create_role(self, client, test_user_with_role, test_tenant):
        """Test access denied when user lacks MANAGE_ROLES permission"""
        # Ensure user has basic permissions but not MANAGE_ROLES
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.setup_basic_permissions(user_role.role)

        # Login
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user_with_role.email, "password": "password123"},
            headers=headers,
        )

        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        # Test endpoint
        new_role_data = {
            "name": "custom-role",
            "description": "Custom role for testing",
            "permissions": {Permission.VIEW_TENANT.value: True},
        }

        response = client.post(
            f"/api/tenants/{test_tenant.id}/roles", json=new_role_data, headers=headers
        )

        assert response.status_code == 403
