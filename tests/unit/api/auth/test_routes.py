# tests/unit/api/auth/test_routes.py
import pytest
from unittest.mock import patch
from app.models.user import User
from app.models.tenant import Tenant
from app.models.role import Role
from app.models.user_tenant_role import UserTenantRole
from app.extensions import db
from app.core.rate_limiter import RateLimiter


@pytest.fixture
def rate_limiter(app, fake_redis):
    """Create a rate limiter with fake Redis"""
    app.config["RATE_LIMIT_ENABLED"] = True
    app.config["REDIS_URL"] = "redis://fake"
    limiter = RateLimiter()
    limiter.init_app(app)
    limiter.redis = fake_redis
    return limiter


@pytest.fixture
def test_tenant(app):
    with app.app_context():
        try:
            db.session.begin_nested()
            tenant = Tenant(name="Test Business", subdomain="test-business", is_active=True)
            db.session.add(tenant)
            db.session.commit()

            yield tenant

            db.session.begin_nested()
            UserTenantRole.query.filter_by(tenant_id=tenant.id).delete()
            db.session.delete(tenant)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise


@pytest.fixture
def test_role(app, test_tenant):
    with app.app_context():
        try:
            db.session.begin_nested()
            role = Role(name="owner", tenant_id=test_tenant.id, permissions={"admin": True})
            db.session.add(role)
            db.session.commit()

            yield role

            db.session.begin_nested()
            UserTenantRole.query.filter_by(role_id=role.id).delete()
            db.session.delete(role)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise


@pytest.fixture
def test_user(app, test_tenant, test_role):
    with app.app_context():
        try:
            db.session.begin_nested()
            user = User(email="test@example.com", first_name="Test", last_name="User", is_active=True)
            user.password = "password123"
            db.session.add(user)
            db.session.commit()

            tenant_role = UserTenantRole(
                user_id=user.id,
                tenant_id=test_tenant.id,
                role_id=test_role.id,
                is_primary=True,
                is_active=True,
            )
            db.session.add(tenant_role)
            db.session.commit()

            yield user

            db.session.begin_nested()
            UserTenantRole.query.filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise


class TestAuthRoutes:
    def test_login_success(self, client, test_user, test_tenant, rate_limiter):
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["user"]["email"] == test_user.email
        assert data["user"]["primary_tenant"]["subdomain"] == test_tenant.subdomain

    def test_login_rate_limit(self, client, test_user, test_tenant, rate_limiter, fake_redis):
        fake_redis.flushall()
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}

        # Make 5 failed login attempts
        for i in range(5):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrong_password"},
                headers=headers,
            )
            assert response.status_code == 401
            assert int(response.headers["X-RateLimit-Remaining"]) == 4 - i

        # 6th attempt should be rate limited
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrong_password"},
            headers=headers,
        )
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.get_json()["error"]

    def test_login_wrong_tenant(self, client, test_user, app):
        with app.app_context():
            try:
                db.session.begin_nested()
                other_tenant = Tenant(name="Other Business", subdomain="other-business", is_active=True)
                db.session.add(other_tenant)
                db.session.commit()

                headers = {"Host": f"{other_tenant.subdomain}.example.com"}
                response = client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "password123"},
                    headers=headers,
                )

                assert response.status_code == 403
                data = response.get_json()
                assert "No access to this tenant" in data.get("message", "")

            finally:
                db.session.begin_nested()
                db.session.delete(other_tenant)
                db.session.commit()

    def test_google_auth(self, client, test_tenant, test_role, rate_limiter):
        with patch("app.api.auth.routes.verify_google_token") as mock_verify:
            mock_verify.return_value = {
                "sub": "12345",
                "email": "google@example.com",
                "email_verified": True,
                "given_name": "Google",
                "family_name": "User",
            }

            headers = {"Host": f"{test_tenant.subdomain}.example.com"}

            # Create user role
            with db.session.begin_nested():
                user_role = Role(name="user", tenant_id=test_tenant.id, permissions={"basic": True})
                db.session.add(user_role)
                db.session.commit()

            try:
                response = client.post("/api/auth/google", json={"token": "fake_token"}, headers=headers)

                assert response.status_code == 200
                data = response.get_json()
                assert "token" in data
                assert "user" in data

                user_data = data["user"]
                assert user_data["email"] == "google@example.com"
                assert user_data["first_name"] == "Google"
                assert user_data["last_name"] == "User"

                # Cleanup created user
                user = User.query.filter_by(google_id="12345").first()
                if user:
                    db.session.begin_nested()
                    UserTenantRole.query.filter_by(user_id=user.id).delete()
                    db.session.delete(user)
                    db.session.commit()

            finally:
                db.session.begin_nested()
                db.session.delete(user_role)
                db.session.commit()

    def test_me_endpoint(self, client, test_user, test_tenant, rate_limiter):
        # Login first
        headers = {"Host": f"{test_tenant.subdomain}.example.com"}
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
            headers=headers,
        )

        token = login_response.get_json()["token"]
        headers["Authorization"] = f"Bearer {token}"

        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["email"] == test_user.email
        assert data["primary_tenant"]["subdomain"] == test_tenant.subdomain

    def test_switch_tenant(self, client, test_user, test_tenant, rate_limiter, app):
        with app.app_context():
            try:
                db.session.begin_nested()
                # Create second tenant and role
                tenant2 = Tenant(name="Second Business", subdomain="second-business")
                db.session.add(tenant2)
                db.session.commit()

                role2 = Role(name="user", tenant_id=tenant2.id)
                db.session.add(role2)
                db.session.commit()

                tenant_role2 = UserTenantRole(
                    user_id=test_user.id,
                    tenant_id=tenant2.id,
                    role_id=role2.id,
                    is_primary=False
                )
                db.session.add(tenant_role2)
                db.session.commit()

                # Login and switch tenant
                headers = {"Host": f"{test_tenant.subdomain}.example.com"}
                login_response = client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "password123"},
                    headers=headers,
                )

                token = login_response.get_json()["token"]
                headers["Authorization"] = f"Bearer {token}"

                response = client.post(
                    "/api/auth/switch-tenant",
                    json={"tenant_id": tenant2.id},
                    headers=headers
                )

                assert response.status_code == 200
                data = response.get_json()
                assert data["user"]["primary_tenant"]["id"] == tenant2.id

            finally:
                db.session.begin_nested()
                UserTenantRole.query.filter_by(tenant_id=tenant2.id).delete()
                db.session.delete(role2)
                db.session.delete(tenant2)
                db.session.commit()