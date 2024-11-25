# tests/unit/api/user/test_routes.py

from uuid import uuid4
import pytest
from app.models import User, Role, UserTenantRole
from app.core.constants import Permission
from app.extensions import db


class TestUserRoutes:
    def setup_method(self, method):
        """Setup method that runs before each test"""
        db.session.query(UserTenantRole).delete()
        db.session.commit()

    def ensure_user_tenant_role(self, user, tenant, permissions=None):
        """Helper to ensure user has a role in the tenant"""
        user_role = db.session.execute(
            db.select(UserTenantRole)
            .filter_by(user_id=user.id, tenant_id=tenant.id)
        ).scalar_one_or_none()

        if not user_role:
            role = db.session.execute(
                db.select(Role).filter_by(tenant_id=tenant.id)
            ).scalar_one_or_none()

            if not role:
                role = Role(
                    id=str(uuid4()),
                    name='test_role',
                    tenant_id=tenant.id
                )
                db.session.add(role)
                db.session.commit()

            user_role = UserTenantRole(
                id=str(uuid4()),
                user_id=user.id,
                tenant_id=tenant.id,
                role_id=role.id,
                is_primary=True
            )
            db.session.add(user_role)
            db.session.commit()

        if permissions:
            user_role.role.permissions = permissions
            db.session.commit()

        return user_role

    def ensure_admin_permissions(self, user_role):
        """Helper to set up admin permissions"""
        user_role.role.permissions = {
            'admin': True,
            Permission.VIEW_USERS.value: True,
            Permission.MANAGE_USERS.value: True,
            Permission.VIEW_TENANT.value: True
        }
        db.session.commit()

    def test_list_users(self, client, test_user_with_role, test_tenant):
        # Ensure admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.ensure_admin_permissions(user_role)

        # Login
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': test_user_with_role.email,
                'password': 'password123'
            },
            headers=headers
        )

        assert login_response.status_code == 200
        token = login_response.get_json()['token']
        headers['Authorization'] = f'Bearer {token}'

        # Test endpoint
        response = client.get('/api/users', headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert 'total' in data
        assert 'pages' in data
        assert len(data['users']) >= 1

    def test_create_user(self, client, test_user_with_role, test_tenant):
        # Ensure admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.ensure_admin_permissions(user_role)

        # Login
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': test_user_with_role.email,
                'password': 'password123'
            },
            headers=headers
        )

        assert login_response.status_code == 200
        token = login_response.get_json()['token']
        headers['Authorization'] = f'Bearer {token}'

        # Get a role for the new user
        role = db.session.execute(
            db.select(Role).filter_by(tenant_id=test_tenant.id)
        ).scalar_one()

        # Test endpoint
        new_user_data = {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role_id': role.id,
            'password': 'password123'
        }

        response = client.post('/api/users', json=new_user_data, headers=headers)
        assert response.status_code == 201
        data = response.get_json()
        assert data['email'] == new_user_data['email']
        assert 'id' in data

        # Clean up
        created_user = db.session.execute(
            db.select(User).filter_by(email='newuser@example.com')
        ).scalar_one_or_none()

        if created_user:
            db.session.query(UserTenantRole).filter_by(user_id=created_user.id).delete()
            db.session.delete(created_user)
            db.session.commit()

    def test_get_user(self, client, test_user_with_role, test_tenant):
        # Ensure admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.ensure_admin_permissions(user_role)

        # Login
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': test_user_with_role.email,
                'password': 'password123'
            },
            headers=headers
        )

        assert login_response.status_code == 200
        token = login_response.get_json()['token']
        headers['Authorization'] = f'Bearer {token}'

        # Test endpoint
        response = client.get(
            f'/api/users/{test_user_with_role.id}',
            headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == test_user_with_role.email
        assert data['id'] == test_user_with_role.id

    def test_update_user(self, client, test_user_with_role, test_tenant):
        # Ensure admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.ensure_admin_permissions(user_role)

        # Login
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': test_user_with_role.email,
                'password': 'password123'
            },
            headers=headers
        )

        assert login_response.status_code == 200
        token = login_response.get_json()['token']
        headers['Authorization'] = f'Bearer {token}'

        # Test endpoint
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }

        response = client.put(
            f'/api/users/{test_user_with_role.id}',
            json=update_data,
            headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['first_name'] == update_data['first_name']
        assert data['last_name'] == update_data['last_name']

    # tests/unit/api/user/test_routes.py

    def test_update_user_role(self, client, test_user_with_role, test_tenant):
        """Test updating a user's role in a tenant"""
        # Ensure admin permissions
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        self.ensure_admin_permissions(user_role)

        # Create a new role for testing with proper tenant association
        new_role = Role(
            id=str(uuid4()),
            name='new_test_role',
            tenant_id=test_tenant.id,  # Make sure to set the tenant_id
            permissions={}
        )
        db.session.add(new_role)
        db.session.commit()

        # Login
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': test_user_with_role.email,
                'password': 'password123'
            },
            headers=headers
        )

        assert login_response.status_code == 200
        token = login_response.get_json()['token']
        headers['Authorization'] = f'Bearer {token}'

        # Test endpoint
        response = client.put(
            f'/api/users/{test_user_with_role.id}/role',
            json={'role_id': new_role.id},
            headers=headers
        )

        assert response.status_code == 200

        # Verify role was updated
        updated_user_role = db.session.execute(
            db.select(UserTenantRole)
            .filter_by(user_id=test_user_with_role.id, tenant_id=test_tenant.id)
        ).scalar_one()
        assert updated_user_role.role_id == new_role.id

        # Clean up
        try:
            db.session.delete(new_role)
            db.session.commit()
        except:
            db.session.rollback()

    def test_permission_denied_manage_users(self, client, test_user_with_role, test_tenant):
        # Ensure user has basic permissions but not MANAGE_USERS
        user_role = self.ensure_user_tenant_role(test_user_with_role, test_tenant)
        user_role.role.permissions = {
            Permission.VIEW_USERS.value: True,
            Permission.VIEW_TENANT.value: True
        }
        db.session.commit()

        # Login
        headers = {'Host': f'{test_tenant.subdomain}.example.com'}
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': test_user_with_role.email,
                'password': 'password123'
            },
            headers=headers
        )

        assert login_response.status_code == 200
        token = login_response.get_json()['token']
        headers['Authorization'] = f'Bearer {token}'

        # Test create endpoint (should be denied)
        new_user_data = {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'role_id': user_role.role_id
        }
        response = client.post('/api/users', json=new_user_data, headers=headers)
        assert response.status_code == 403

        # Test update endpoint (should be denied)
        response = client.put(
            f'/api/users/{test_user_with_role.id}',
            json={'first_name': 'Updated'},
            headers=headers
        )
        assert response.status_code == 403