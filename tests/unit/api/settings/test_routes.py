# tests/unit/api/settings/test_routes.py
import pytest
from app.models.settings import Settings
from app.extensions import db


def test_get_settings(client, auth_headers, test_tenant, test_settings):
    """Test getting settings"""
    response = client.get(
        f'/api/settings/tenant/{test_tenant.id}',
        headers=auth_headers
    )
    assert response.status_code == 200
    assert 'settings' in response.json
    assert response.json['settings']['theme'] == 'light'
    assert response.json['settings']['notifications'] is True


def test_update_settings(client, auth_headers, test_tenant):
    """Test updating multiple settings"""
    test_settings = {
        'theme': 'dark',
        'notifications': True,
        'language': 'en'
    }

    response = client.put(
        f'/api/settings/tenant/{test_tenant.id}',
        json={'settings': test_settings},
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json['settings'] == test_settings


def test_update_single_setting(client, auth_headers, test_tenant, test_settings):
    """Test updating a single setting"""
    response = client.put(
        f'/api/settings/tenant/{test_tenant.id}/theme',
        json={'key': 'theme', 'value': 'dark'},
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json['value'] == 'dark'


def test_delete_setting(client, auth_headers, test_tenant, test_settings):
    """Test deleting a setting"""
    response = client.delete(
        f'/api/settings/tenant/{test_tenant.id}/theme',
        headers=auth_headers
    )

    assert response.status_code == 204
    settings = Settings.get_for_owner('tenant', test_tenant.id)
    assert 'theme' not in settings.settings


def test_unauthorized_access(client, test_tenant):
    """Test accessing settings without authentication"""
    response = client.get(
        f'/api/settings/tenant/{test_tenant.id}',
    )
    assert response.status_code == 401


def test_create_settings_for_new_owner(client, auth_headers, test_tenant):
    """Test creating settings for an owner that doesn't have any yet"""
    new_settings = {'theme': 'dark'}

    response = client.put(
        f'/api/settings/tenant/{test_tenant.id}',
        json={'settings': new_settings},
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json['settings'] == new_settings