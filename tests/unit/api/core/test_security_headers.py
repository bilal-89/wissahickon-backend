# tests/unit/api/core/test_security_headers.py

import pytest
from flask import Flask
from app.core.security.security_headers import SecurityHeaders, init_security_headers


@pytest.fixture
def app():
    """Create test Flask app with security headers"""
    app = Flask(__name__)
    init_security_headers(app)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


def test_basic_security_headers(client):
    """Test that basic security headers are set"""
    response = client.get("/")

    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers


def test_content_security_policy(client):
    """Test Content Security Policy header"""
    response = client.get("/")
    csp = response.headers["Content-Security-Policy"]

    # Check essential CSP directives
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp


def test_hsts_in_production(app, client):
    """Test HSTS header in production environment"""
    # Set app to production mode
    app.debug = False

    response = client.get("/")
    hsts = response.headers["Strict-Transport-Security"]

    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


def test_hsts_not_in_development(app, client):
    """Test HSTS header not present in development"""
    # Ensure debug mode is on
    app.debug = True

    response = client.get("/")
    assert "Strict-Transport-Security" not in response.headers


def test_permissions_policy(client):
    """Test Permissions Policy header"""
    response = client.get("/")
    permissions = response.headers["Permissions-Policy"]

    assert "geolocation=()" in permissions
    assert "microphone=()" in permissions
    assert "camera=()" in permissions


def test_all_responses_have_headers(client):
    """Test that all response types have security headers"""
    # Test different HTTP methods
    for method in ["get", "post", "put", "delete"]:
        client_method = getattr(client, method)
        response = client_method("/")

        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "X-Content-Type-Options" in response.headers


def test_error_responses_have_headers(app, client):
    """Test that error responses also have security headers"""

    @app.route("/error")
    def trigger_error():
        return {"error": "test"}, 400

    response = client.get("/error")
    assert response.status_code == 400
    assert "X-Frame-Options" in response.headers
    assert "Content-Security-Policy" in response.headers


def test_custom_response_types(app, client):
    """Test headers are set for different response types"""

    @app.route("/json")
    def json_response():
        return {"data": "test"}

    @app.route("/text")
    def text_response():
        return "test"

    # Test JSON response
    json_resp = client.get("/json")
    assert "X-Frame-Options" in json_resp.headers

    # Test text response
    text_resp = client.get("/text")
    assert "X-Frame-Options" in text_resp.headers


def test_csp_allows_required_sources(client):
    """Test that CSP allows required external sources"""
    response = client.get("/")
    csp = response.headers["Content-Security-Policy"]

    # Check for required external sources
    assert "https://cdnjs.cloudflare.com" in csp
    assert "data:" in csp
