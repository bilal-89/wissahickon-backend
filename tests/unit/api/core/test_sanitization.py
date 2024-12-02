# tests/unit/api/core/test_sanitization.py
import pytest
from flask import Flask, request, jsonify
import json
from app.core.security.sanitization import RequestSanitizer, sanitize_request


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB limit

    @app.route("/api/test", methods=["POST"])
    @sanitize_request()
    def test_endpoint():
        if request.is_json:
            return jsonify(request.get_json())
        elif request.form:
            return jsonify(dict(request.form))
        return jsonify({})

    @app.route("/api/test_exempt", methods=["POST"])
    @sanitize_request(exempt_paths=[r"/api/test_exempt"])
    def exempt_endpoint():
        if request.is_json:
            return jsonify(request.get_json())
        return jsonify(dict(request.form))

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def clean_app_context(app):
    with app.app_context():
        yield


def test_basic_sanitization(client, clean_app_context):
    """Test basic string sanitization"""
    data = {"name": "John<script>alert('xss')</script>Doe", "email": "john@example.com"}

    response = client.post("/api/test", json=data, content_type="application/json")

    assert response.status_code == 200
    result = response.get_json()
    assert "script" not in result["name"]
    assert result["email"] == "john@example.com"


def test_nested_sanitization(client, clean_app_context):
    """Test sanitization of nested objects"""
    data = {
        "user": {
            "name": "John<script>alert('xss')</script>Doe",
            "profile": {"bio": "<img src=x onerror=alert('xss')>Bio text"},
        }
    }

    response = client.post("/api/test", json=data, content_type="application/json")

    assert response.status_code == 200
    result = response.get_json()
    assert "script" not in result["user"]["name"]
    assert "img" not in result["user"]["profile"]["bio"]
    assert "Bio text" in result["user"]["profile"]["bio"]


def test_array_sanitization(client, clean_app_context):
    """Test sanitization of arrays"""
    data = {
        "names": [
            "John<script>alert('xss')</script>",
            "Jane<img src=x onerror=alert('xss')>",
            "Bob",
        ]
    }

    response = client.post("/api/test", json=data, content_type="application/json")

    assert response.status_code == 200
    result = response.get_json()
    assert all("script" not in name for name in result["names"])
    assert all("img" not in name for name in result["names"])
    assert "Bob" in result["names"]


def test_content_type_validation(client, clean_app_context):
    """Test content type validation"""
    data = {"name": "John"}

    # Test invalid content type
    response = client.post("/api/test", data=json.dumps(data), content_type="application/xml")
    assert response.status_code == 415

    # Test valid content type
    response = client.post("/api/test", json=data, content_type="application/json")
    assert response.status_code == 200


def test_content_length_validation(client, clean_app_context):
    """Test content length validation"""
    large_data = {"data": "x" * (11 * 1024 * 1024)}  # 11MB

    response = client.post("/api/test", json=large_data, content_type="application/json")
    assert response.status_code == 413


def test_exempt_paths(client, clean_app_context):
    """Test path exemption"""
    data = {"name": "John<script>alert('xss')</script>Doe"}

    # Test exempt endpoint
    response = client.post("/api/test_exempt", json=data, content_type="application/json")

    assert response.status_code == 200
    result = response.get_json()
    assert "script" in result["name"]  # Script tag should remain as path is exempt


def test_allowed_html_tags(client, clean_app_context):
    """Test that allowed HTML tags are preserved"""
    data = {
        "content": "<p>This is <strong>bold</strong> and <em>italic</em></p><script>alert('xss')</script>"
    }

    response = client.post("/api/test", json=data, content_type="application/json")

    assert response.status_code == 200
    result = response.get_json()
    assert "<p>" in result["content"]
    assert "<strong>" in result["content"]
    assert "<em>" in result["content"]
    assert "<script>" not in result["content"]


def test_null_byte_handling(client, clean_app_context):
    """Test handling of null bytes"""
    data = {"name": "John\x00Doe\x00"}

    response = client.post("/api/test", json=data, content_type="application/json")

    assert response.status_code == 200
    result = response.get_json()
    assert "\x00" not in result["name"]
    assert result["name"] == "JohnDoe"


def test_invalid_json(client, clean_app_context):
    """Test handling of invalid JSON"""
    response = client.post("/api/test", data="invalid{json", content_type="application/json")

    assert response.status_code == 400


def test_form_data_sanitization(client, clean_app_context):
    """Test sanitization of form data"""
    data = {"name": "John<script>alert('xss')</script>Doe", "email": "john@example.com"}

    response = client.post("/api/test", data=data, content_type="application/x-www-form-urlencoded")

    assert response.status_code == 200
    result = response.get_json()
    assert "script" not in result["name"]
    assert result["email"] == "john@example.com"


def test_mixed_content(client, clean_app_context):
    """Test handling of mixed content types"""
    data = {
        "name": "<p>John<script>alert('xss')</script>Doe</p>",
        "numbers": [1, 2, "<script>alert(3)</script>"],
        "nested": {"bio": "<strong>Hello</strong><img src=x onerror=alert('xss')>"},
    }

    response = client.post("/api/test", json=data, content_type="application/json")

    assert response.status_code == 200
    result = response.get_json()
    assert "script" not in result["name"]
    assert "<p>" in result["name"]
    assert "script" not in str(result["numbers"])
    assert "<strong>" in result["nested"]["bio"]
    assert "img" not in result["nested"]["bio"]
