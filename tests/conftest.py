# conftest.py

from app.models import User, Tenant, Role, UserTenantRole
from uuid import uuid4
import pytest
from app import create_app
from app.extensions import db
from app.models.settings import Settings
from flask_jwt_extended import create_access_token
from flask import current_app
from app.core.rate_limiter import RateLimiter
import fakeredis


@pytest.fixture(scope="session")
def fake_redis():
    """Create a fake Redis instance for testing"""
    return fakeredis.FakeStrictRedis()


@pytest.fixture(scope="session")
def app(fake_redis):
    """Create test Flask app with rate limiting support"""
    app = create_app("testing")
    app.config.update(
        {
            "REDIS_URL": "redis://fake",  # Add Redis URL to config
            "RATE_LIMIT_ENABLED": True,  # Enable rate limiting in tests
        }
    )

    # Initialize rate limiter with fake redis
    limiter = RateLimiter(redis_url="redis://fake")
    limiter.init_app(app)
    limiter.redis = fake_redis  # Use our fake redis instance

    print(f"Using database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    print(f"Using database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app):
    with app.app_context():
        try:
            db.session.begin_nested()
            user = User(
                id=str(uuid4()), email="test@example.com", first_name="Test", last_name="User"
            )
            user.password = "password123"
            db.session.add(user)
            db.session.commit()

            yield user

            db.session.begin_nested()
            db.session.query(UserTenantRole).filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error in test_user fixture: {str(e)}")
            db.session.rollback()
            raise


@pytest.fixture
def test_tenant(app):
    with app.app_context():
        try:
            db.session.begin_nested()
            tenant = Tenant(
                id=str(uuid4()), name="Test Business", subdomain="test-business", is_active=True
            )
            db.session.add(tenant)
            db.session.commit()

            yield tenant

            db.session.begin_nested()
            db.session.query(UserTenantRole).filter_by(tenant_id=tenant.id).delete()
            db.session.query(Role).filter_by(tenant_id=tenant.id).delete()
            db.session.delete(tenant)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error in test_tenant fixture: {str(e)}")
            db.session.rollback()
            raise


@pytest.fixture
def test_role(app, test_tenant):
    with app.app_context():
        try:
            db.session.begin_nested()
            role = Role(
                id=str(uuid4()), name="admin", tenant_id=test_tenant.id, permissions={"admin": True}
            )
            db.session.add(role)
            db.session.commit()

            yield role

            db.session.begin_nested()
            db.session.query(Role).filter_by(id=role.id).delete()
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error in test_role fixture: {str(e)}")
            db.session.rollback()
            raise


@pytest.fixture
def test_user_with_role(app, test_user, test_tenant, test_role):
    """Assign the test user to the test tenant with the test role"""
    with app.app_context():
        try:
            db.session.begin_nested()
            user_tenant_role = UserTenantRole(
                user_id=test_user.id,
                tenant_id=test_tenant.id,
                role_id=test_role.id,
                is_primary=True,
            )
            db.session.add(user_tenant_role)
            db.session.commit()

            yield test_user

            db.session.begin_nested()
            db.session.query(UserTenantRole).filter_by(user_id=test_user.id).delete()
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error in test_user_with_role fixture: {str(e)}")
            db.session.rollback()
            raise


@pytest.fixture
def second_tenant(app, test_tenant, test_user_with_role, test_role):
    """Create a second tenant and assign test_user to it with a different role"""
    try:
        db.session.begin_nested()
        tenant = Tenant(
            id=str(uuid4()), name="Second Business", subdomain="second-business", is_active=True
        )
        db.session.add(tenant)
        db.session.commit()

        db.session.begin_nested()
        role = Role(id=str(uuid4()), name="user", tenant_id=tenant.id, permissions={"basic": True})
        db.session.add(role)
        db.session.commit()

        db.session.begin_nested()
        tenant_role = UserTenantRole(
            user_id=test_user_with_role.id, tenant_id=tenant.id, role_id=role.id, is_primary=False
        )
        db.session.add(tenant_role)
        db.session.commit()

        yield tenant

        db.session.begin_nested()
        db.session.query(UserTenantRole).filter_by(tenant_id=tenant.id).delete()
        db.session.delete(role)
        db.session.delete(tenant)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error in second_tenant fixture: {str(e)}")
        db.session.rollback()
        raise


@pytest.fixture
def auth_headers(test_user_with_role):
    """Create authentication headers with JWT token"""
    token = create_access_token(identity=test_user_with_role.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_settings(test_tenant):
    """Create test settings for a tenant"""
    try:
        db.session.begin_nested()
        settings = Settings(
            owner_type="tenant",
            owner_id=test_tenant.id,
            settings={"theme": "light", "notifications": True},
        )
        db.session.add(settings)
        db.session.commit()
        return settings
    except Exception as e:
        current_app.logger.error(f"Error in test_settings fixture: {str(e)}")
        db.session.rollback()
        raise


# Clean up settings after tests
@pytest.fixture(autouse=True)
def cleanup_settings(app):
    """Clean up settings after each test"""
    yield
    with app.app_context():
        try:
            db.session.begin_nested()
            Settings.query.delete()
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error in cleanup_settings: {str(e)}")
            db.session.rollback()
        finally:
            db.session.close()
