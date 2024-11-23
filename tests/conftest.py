from app.models import User, Tenant, Role
from uuid import uuid4
import pytest
from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def sample_user(app):
    with app.app_context():
        user = User(
            id=str(uuid4()),
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        db.session.add(user)
        db.session.commit()
        yield user
        db.session.delete(user)
        db.session.commit()

@pytest.fixture
def sample_tenants(app):
    with app.app_context():
        # Create test tenants
        zen_garden = Tenant(
            id=str(uuid4()),
            name="Zen Garden Yoga",
            subdomain="zengarden"
        )
        consulting = Tenant(
            id=str(uuid4()),
            name="Bob's Consulting",
            subdomain="bobconsulting"
        )
        db.session.add_all([zen_garden, consulting])
        db.session.commit()
        
        yield {
            'zen_garden': zen_garden,
            'consulting': consulting
        }
        
        # Cleanup
        db.session.query(Tenant).delete()
        db.session.commit()

@pytest.fixture
def sample_roles(app, sample_tenants):
    with app.app_context():
        # Create roles for each tenant
        zen_owner = Role(
            id=str(uuid4()),
            name="owner",
            tenant_id=sample_tenants['zen_garden'].id,
            permissions={"full_access": True}
        )
        zen_staff = Role(
            id=str(uuid4()),
            name="staff",
            tenant_id=sample_tenants['zen_garden'].id,
            permissions={"staff_access": True}
        )
        consulting_client = Role(
            id=str(uuid4()),
            name="client",
            tenant_id=sample_tenants['consulting'].id,
            permissions={"client_access": True}
        )
        
        db.session.add_all([zen_owner, zen_staff, consulting_client])
        db.session.commit()
        
        yield {
            'zen_owner': zen_owner,
            'zen_staff': zen_staff,
            'consulting_client': consulting_client
        }
        
        db.session.query(Role).delete()
        db.session.commit()


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')

    print(f"Using database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")  # Debug print

    with app.app_context():
        # Drop all tables if they exist
        db.drop_all()
        # Create all tables
        db.create_all()
        yield app
        # Cleanup
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()