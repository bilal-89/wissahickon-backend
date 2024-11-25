# conftest.py

from app.models import User, Tenant, Role, UserTenantRole
from uuid import uuid4
import pytest
from app import create_app
from app.extensions import db


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')

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
        user = User(
            id=str(uuid4()),
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        user.password = "password123"
        db.session.add(user)
        db.session.commit()

        yield user

        db.session.query(UserTenantRole).filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()


@pytest.fixture
def test_tenant(app):
    with app.app_context():
        tenant = Tenant(
            id=str(uuid4()),
            name="Test Business",
            subdomain="test-business",
            is_active=True
        )
        db.session.add(tenant)
        db.session.commit()

        yield tenant

        db.session.query(UserTenantRole).filter_by(tenant_id=tenant.id).delete()
        db.session.query(Role).filter_by(tenant_id=tenant.id).delete()
        db.session.delete(tenant)
        db.session.commit()


@pytest.fixture
def test_role(app, test_tenant):
    with app.app_context():
        role = Role(
            id=str(uuid4()),
            name="admin",
            tenant_id=test_tenant.id,
            permissions={"admin": True}
        )
        db.session.add(role)
        db.session.commit()

        yield role

        db.session.query(Role).filter_by(id=role.id).delete()
        db.session.commit()


@pytest.fixture
def test_user_with_role(app, test_user, test_tenant, test_role):
    """Assign the test user to the test tenant with the test role"""
    with app.app_context():
        user_tenant_role = UserTenantRole(
            user_id=test_user.id,
            tenant_id=test_tenant.id,
            role_id=test_role.id,
            is_primary=True
        )
        db.session.add(user_tenant_role)
        db.session.commit()

        yield test_user

        db.session.query(UserTenantRole).filter_by(user_id=test_user.id).delete()
        db.session.commit()


@pytest.fixture
def second_tenant(app, test_tenant, test_user_with_role, test_role):
    """Create a second tenant and assign test_user to it with a different role"""
    tenant = Tenant(
        id=str(uuid4()),
        name="Second Business",
        subdomain="second-business",
        is_active=True
    )
    db.session.add(tenant)
    db.session.commit()

    role = Role(
        id=str(uuid4()),
        name="user",
        tenant_id=tenant.id,
        permissions={"basic": True}
    )
    db.session.add(role)
    db.session.commit()

    tenant_role = UserTenantRole(
        user_id=test_user_with_role.id,
        tenant_id=tenant.id,
        role_id=role.id,
        is_primary=False
    )
    db.session.add(tenant_role)
    db.session.commit()

    yield tenant

    db.session.query(UserTenantRole).filter_by(tenant_id=tenant.id).delete()
    db.session.delete(role)
    db.session.delete(tenant)
    db.session.commit()