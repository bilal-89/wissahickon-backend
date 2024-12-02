# tests/unit/api/health/test_routes.py

import pytest
from unittest.mock import patch
from redis import Redis
from sqlalchemy import text


def test_basic_health_check(client):
    """Test basic health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json

    assert data["status"] == "healthy"
    assert "response_time" in data
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]


def test_health_check_with_db_failure(client):
    """Test health check when database is down"""
    with patch("app.api.health.routes.check_database", return_value=(False, "DB Error")):
        response = client.get("/api/health")
        assert response.status_code == 503
        data = response.json
        assert data["status"] == "unhealthy"
        assert data["services"]["database"]["status"] == "unhealthy"


def test_health_check_with_redis_failure(client):
    """Test health check when Redis is down"""
    with patch("app.api.health.routes.check_redis", return_value=(False, "Redis Error")):
        response = client.get("/api/health")
        assert response.status_code == 503
        data = response.json
        assert data["status"] == "unhealthy"
        assert data["services"]["redis"]["status"] == "unhealthy"


def test_extended_health_check(client):
    """Test extended health check endpoint"""
    response = client.get("/api/health/extended")
    assert response.status_code == 200
    data = response.json

    assert data["status"] == "healthy"
    assert "system" in data
    assert "memory_usage" in data["system"]
    assert "services" in data
