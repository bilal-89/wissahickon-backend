# tests/core/test_request_validation.py

import pytest
from flask import Flask, request, jsonify
from app.core.validation import RequestValidator


@pytest.fixture
def app():
    app = Flask(__name__)

    @app.route('/test', methods=['POST'])
    @RequestValidator.validate_json({
        'email': {
            'type': str,
            'required': True,
            'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'max_length': 255
        },
        'name': {
            'type': str,
            'required': True,
            'max_length': 100,
            'min_length': 2
        },
        'age': {
            'type': int,
            'required': False
        }
    })
    def test_endpoint():
        return jsonify({'status': 'success'})

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_valid_request(client):
    """Test that valid request data passes validation"""
    response = client.post('/test',
                           json={
                               'email': 'test@example.com',
                               'name': 'John Doe',
                               'age': 30
                           }
                           )
    assert response.status_code == 200


def test_invalid_content_type(client):
    """Test that non-JSON requests are rejected"""
    response = client.post('/test',
                           data='not json'
                           )
    assert response.status_code == 400
    assert b'Content-Type must be application/json' in response.data


def test_missing_required_field(client):
    """Test that missing required fields are caught"""
    response = client.post('/test',
                           json={
                               'email': 'test@example.com'
                               # missing required 'name' field
                           }
                           )
    assert response.status_code == 400
    assert b'Missing required field: name' in response.data


def test_invalid_email_format(client):
    """Test email format validation"""
    response = client.post('/test',
                           json={
                               'email': 'not-an-email',
                               'name': 'John Doe'
                           }
                           )
    assert response.status_code == 400
    assert b'Invalid format for field email' in response.data


def test_string_too_long(client):
    """Test maximum length validation"""
    response = client.post('/test',
                           json={
                               'email': 'test@example.com',
                               'name': 'x' * 101  # exceeds max_length of 100
                           }
                           )
    assert response.status_code == 400
    assert b'exceeds maximum length' in response.data


def test_string_too_short(client):
    """Test minimum length validation"""
    response = client.post('/test',
                           json={
                               'email': 'test@example.com',
                               'name': 'a'  # shorter than min_length of 2
                           }
                           )
    assert response.status_code == 400
    assert b'shorter than minimum length' in response.data


def test_invalid_type(client):
    """Test type validation"""
    response = client.post('/test',
                           json={
                               'email': 'test@example.com',
                               'name': 'John Doe',
                               'age': 'thirty'  # should be integer
                           }
                           )
    assert response.status_code == 400
    assert b'Invalid type for field age' in response.data


def test_sanitize_string():
    """Test string sanitization"""
    result = RequestValidator.sanitize_string(" Hello\n\tWorld  ")
    assert result == "Hello\nWorld"

    result = RequestValidator.sanitize_string("Too Long", max_length=5)
    assert result == "Too L"