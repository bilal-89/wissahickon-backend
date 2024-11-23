import pytest
from app.models import User, Tenant, Role, UserTenantRole
from app.extensions import db
from uuid import uuid4

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
        db.session.query(UserTenantRole).delete()
        db.session.query(User).delete()
        db.session.query(Role).delete()
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

def test_user_tenant_role_creation(app, sample_tenants, sample_roles):
    """Test basic creation of user with tenant roles"""
    with app.app_context():
        # Create test user
        user = User(
            id=str(uuid4()),
            email="maya@zengardenyoga.com",
            first_name="Maya",
            last_name="Chen"
        )
        db.session.add(user)
        db.session.commit()
        
        # Add Maya as owner of Zen Garden (primary)
        user.add_tenant_role(
            sample_tenants['zen_garden'],
            sample_roles['zen_owner'],
            is_primary=True
        )
        
        # Add Maya as client of consulting
        user.add_tenant_role(
            sample_tenants['consulting'],
            sample_roles['consulting_client']
        )
        
        # Verify relationships using get_tenant_roles()
        tenant_roles = user.get_tenant_roles()
        assert len(tenant_roles) == 2
        
        # Verify primary tenant and role
        assert user.primary_tenant.id == sample_tenants['zen_garden'].id
        assert user.primary_role.name == "owner"
        
        # Verify role lookup
        zen_role = user.get_role_for_tenant(sample_tenants['zen_garden'])
        consulting_role = user.get_role_for_tenant(sample_tenants['consulting'])
        
        assert zen_role.name == "owner"
        assert consulting_role.name == "client"

def test_primary_tenant_switching(app, sample_tenants, sample_roles):
    """Test switching primary tenant"""
    with app.app_context():
        # Create test user with two tenant roles
        user = User(
            id=str(uuid4()),
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        db.session.add(user)
        db.session.commit()
        
        # Add roles
        user.add_tenant_role(
            sample_tenants['zen_garden'],
            sample_roles['zen_staff'],
            is_primary=True
        )
        user.add_tenant_role(
            sample_tenants['consulting'],
            sample_roles['consulting_client']
        )
        
        # Verify initial primary
        assert user.primary_tenant.id == sample_tenants['zen_garden'].id
        
        # Switch primary tenant
        consulting_role = user.tenant_roles.filter_by(
            tenant_id=sample_tenants['consulting'].id
        ).first()
        consulting_role.is_primary = True
        
        # Old primary should be automatically set to false
        zen_role = user.tenant_roles.filter_by(
            tenant_id=sample_tenants['zen_garden'].id
        ).first()
        zen_role.is_primary = False
        
        db.session.commit()
        
        # Verify switch
        assert user.primary_tenant.id == sample_tenants['consulting'].id
        assert len([tr for tr in user.get_tenant_roles() if tr.is_primary]) == 1

def test_tenant_role_validation(app, sample_tenants, sample_roles):
    """Test validation rules for tenant roles"""
    with app.app_context():
        user = User(
            id=str(uuid4()),
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        db.session.add(user)
        db.session.commit()
        
        # Add initial role
        user.add_tenant_role(
            sample_tenants['zen_garden'],
            sample_roles['zen_staff'],
            is_primary=True
        )
        
        # Attempt to add duplicate role - should raise ValueError
        with pytest.raises(ValueError):
            user.add_tenant_role(
                sample_tenants['zen_garden'],
                sample_roles['zen_staff']
            )

def test_user_serialization(app, sample_tenants, sample_roles):
    """Test user JSON serialization with tenant roles"""
    with app.app_context():
        user = User(
            id=str(uuid4()),
            email="maya@zengardenyoga.com",
            first_name="Maya",
            last_name="Chen"
        )
        db.session.add(user)
        db.session.commit()
        
        user.add_tenant_role(
            sample_tenants['zen_garden'],
            sample_roles['zen_owner'],
            is_primary=True
        )
        user.add_tenant_role(
            sample_tenants['consulting'],
            sample_roles['consulting_client']
        )
        
        user_dict = user.to_dict()
        
        # Verify primary tenant/role in serialization
        assert user_dict['primary_tenant']['name'] == "Zen Garden Yoga"
        assert user_dict['primary_tenant']['role'] == "owner"
        
        # Verify other tenants list
        other_tenants = user_dict['other_tenants']
        assert len(other_tenants) == 1
        assert other_tenants[0]['name'] == "Bob's Consulting"
        assert other_tenants[0]['role'] == "client"