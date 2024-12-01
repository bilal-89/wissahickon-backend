# tests/unit/api/auth/test_routes.py
import pytest
from flask import url_for
from app.models.user import User
from app.models.tenant import Tenant
from app.models.role import Role
from app.models.user_tenant_role import UserTenantRole
from app.extensions import db
from unittest.mock import patch
import json
import fakeredis
from app.core.rate_limiter import RateLimiter


@pytest.fixture
def rate_limiter(app):
    """Create a rate limiter with fake Redis"""
    app.config['RATE_LIMIT_ENABLED'] = True
    app.config['REDIS_URL'] = 'redis://fake'

    limiter = RateLimiter()
    limiter.init_app(app)
    # Use fake Redis for testing
    limiter.redis = fakeredis.FakeStrictRedis()

    # Store limiter on app for access in routes
    app.rate_limiter = limiter
    return limiter


@pytest.fixture
def fake_redis():
    """Create a fake Redis instance for testing"""
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def rate_limiter(app, fake_redis):
    """Create a rate limiter with fake Redis"""
    limiter = RateLimiter(redis_url='redis://fake')
    limiter.init_app(app)
    limiter.redis = fake_redis
    return limiter


@pytest.fixture
def test_tenant(app):
    # Create test tenant
    tenant = Tenant(
        name="Test Business",
        subdomain="test-business",
        is_active=True
    )
    db.session.add(tenant)
    db.session.commit()

    yield tenant

    # Clean up - first remove any user_tenant_roles
    UserTenantRole.query.filter_by(tenant_id=tenant.id).delete()
    db.session.commit()

    # Then delete tenant
    db.session.delete(tenant)
    db.session.commit()


@pytest.fixture
def test_role(app, test_tenant):
    role = Role(
        name="owner",
        tenant_id=test_tenant.id,
        permissions={"admin": True}
    )
    db.session.add(role)
    db.session.commit()

    yield role

    # Clean up
    UserTenantRole.query.filter_by(role_id=role.id).delete()
    db.session.commit()
    db.session.delete(role)
    db.session.commit()


@pytest.fixture
def test_user(app, test_tenant, test_role):
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        is_active=True
    )
    user.password = "password123"
    db.session.add(user)
    db.session.commit()

    # Create user_tenant_role relationship
    tenant_role = UserTenantRole(
        user_id=user.id,
        tenant_id=test_tenant.id,
        role_id=test_role.id,
        is_primary=True,
        is_active=True
    )
    db.session.add(tenant_role)
    db.session.commit()

    yield user

    # Clean up - first remove tenant roles
    UserTenantRole.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    # Then delete user
    db.session.delete(user)
    db.session.commit()


class TestAuthRoutes:
    def test_login_success(self, client, test_user, test_tenant):
        # Set tenant subdomain in headers
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}

        response = client.post(
            '/api/auth/login',
            json={
                'email': 'test@example.com',
                'password': 'password123'
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'token' in data
        assert data['user']['email'] == test_user.email
        assert data['user']['primary_tenant']['subdomain'] == test_tenant.subdomain

    def test_login_rate_limit(self, client, test_user, test_tenant, rate_limiter, fake_redis):
        """Test that login endpoint is rate limited"""
        # Clear any existing rate limit data
        fake_redis.flushall()

        headers = {'Host': f'{test_tenant.subdomain}.example.com'}

        # Make 5 failed login attempts (which should be allowed)
        for i in range(5):
            response = client.post(
                '/api/auth/login',
                json={
                    'email': 'test@example.com',
                    'password': 'wrong_password'
                },
                headers=headers
            )

            # Should get unauthorized, not rate limited
            assert response.status_code == 401
            assert 'X-RateLimit-Remaining' in response.headers
            remaining = int(response.headers['X-RateLimit-Remaining'])
            assert remaining == 4 - i  # Should decrease with each request

        # 6th attempt should be rate limited
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'test@example.com',
                'password': 'wrong_password'
            },
            headers=headers
        )

        # Verify rate limit response
        assert response.status_code == 429
        assert 'Rate limit exceeded' in response.get_json()['error']
        assert 'Retry-After' in response.headers

        # Verify successful login still blocked
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'test@example.com',
                'password': 'password123'  # Correct password
            },
            headers=headers
        )

        assert response.status_code == 429

    def test_login_wrong_tenant(self, client, test_user):
        # Create another tenant
        other_tenant = Tenant(
            name="Other Business",
            subdomain="other-business",
            is_active=True
        )
        db.session.add(other_tenant)
        db.session.commit()

        headers = {'Host': f'{other_tenant.subdomain}.example.com'}

        try:
            response = client.post(
                '/api/auth/login',
                json={
                    'email': 'test@example.com',
                    'password': 'password123'
                },
                headers=headers
            )

            assert response.status_code == 403
            data = response.get_json()
            assert 'No access to this tenant' in data.get('message', '')
        finally:
            # Clean up other tenant
            db.session.delete(other_tenant)
            db.session.commit()

    @patch('app.api.auth.routes.verify_google_token')
    def test_google_auth(self, mock_verify, client, test_tenant, test_role):
        # Setup mock response
        mock_verify.return_value = {
            'sub': '12345',
            'email': 'google@example.com',
            'email_verified': True,
            'given_name': 'Google',
            'family_name': 'User'
        }

        # Set up request headers with tenant subdomain
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}

        # Create a user role if needed
        user_role = Role.query.filter_by(name='user', tenant_id=test_tenant.id).first()
        if not user_role:
            user_role = Role(
                name='user',
                tenant_id=test_tenant.id,
                permissions={"basic": True}
            )
            db.session.add(user_role)
            db.session.commit()

        # Make the request
        response = client.post(
            '/api/auth/google',
            json={'token': 'fake_token'},
            headers=headers
        )

        # Verify response
        assert response.status_code == 200
        data = response.get_json()

        # Check basic response structure
        assert 'token' in data
        assert 'user' in data

        # Verify user data
        user_data = data['user']
        assert user_data['email'] == 'google@example.com'
        assert user_data['first_name'] == 'Google'
        assert user_data['last_name'] == 'User'

        # Verify the mock was called correctly
        mock_verify.assert_called_once_with('fake_token')

        # Verify user was created in database
        user = User.query.filter_by(google_id='12345').first()
        assert user is not None
        assert user.email == 'google@example.com'

        # Verify user has correct role in tenant
        tenant_role = user.get_role_for_tenant(test_tenant)
        assert tenant_role is not None

        # Clean up
        if user:
            UserTenantRole.query.filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()

        if user_role:
            db.session.delete(user_role)
            db.session.commit()

    def test_me_endpoint(self, client, test_user, test_tenant):
        # First login to get token
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}

        login_response = client.post(
            '/api/auth/login',
            json={
                'email': 'test@example.com',
                'password': 'password123'
            },
            headers=headers
        )

        token = login_response.get_json()['token']
        headers['Authorization'] = f'Bearer {token}'

        response = client.get('/api/auth/me', headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == test_user.email
        assert data['primary_tenant']['subdomain'] == test_tenant.subdomain

    def test_switch_tenant(self, client, test_user, test_tenant):
        # Create second tenant and role
        tenant2 = Tenant(name="Second Business", subdomain="second-business")
        db.session.add(tenant2)
        db.session.commit()

        role2 = Role(name="user", tenant_id=tenant2.id)
        db.session.add(role2)
        db.session.commit()

        # Add user to second tenant
        tenant_role2 = UserTenantRole(
            user_id=test_user.id,
            tenant_id=tenant2.id,
            role_id=role2.id,
            is_primary=False
        )
        db.session.add(tenant_role2)
        db.session.commit()

        try:
            # Login to get token
            headers = {'Host': f'{test_tenant.subdomain}.example.com'}

            login_response = client.post(
                '/api/auth/login',
                json={
                    'email': 'test@example.com',
                    'password': 'password123'
                },
                headers=headers
            )

            token = login_response.get_json()['token']
            headers['Authorization'] = f'Bearer {token}'

            response = client.post(
                '/api/auth/switch-tenant',
                json={'tenant_id': tenant2.id},
                headers=headers
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['user']['primary_tenant']['id'] == tenant2.id

        finally:
            # Clean up second tenant
            UserTenantRole.query.filter_by(tenant_id=tenant2.id).delete()
            db.session.delete(role2)
            db.session.delete(tenant2)
            db.session.commit()