# tests/unit/api/health/test_routes.py

import pytest
from unittest.mock import patch, MagicMock
from redis import Redis
from sqlalchemy import text


def test_basic_health_check(client):
    """Test basic health check endpoint"""
    # Mock both database and Redis checks to return healthy status
    with patch("app.api.health.routes.check_database", return_value=(True, "Healthy")), \
            patch("app.api.health.routes.check_redis", return_value=(True, "Healthy")):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json

        assert data["status"] == "healthy"
        assert "response_time" in data
        assert "services" in data
        assert "database" in data["services"]
        assert "redis" in data["services"]
        assert data["services"]["database"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "healthy"


def test_health_check_with_db_failure(client):
    """Test health check when database is down"""
    with patch("app.api.health.routes.check_database", return_value=(False, "DB Error")), \
            patch("app.api.health.routes.check_redis", return_value=(True, "Healthy")):
        response = client.get("/api/health")
        assert response.status_code == 503
        data = response.json
        assert data["status"] == "unhealthy"
        assert data["services"]["database"]["status"] == "unhealthy"
        assert data["services"]["database"]["message"] == "DB Error"


def test_health_check_with_redis_failure(client):
    """Test health check when Redis is down"""
    with patch("app.api.health.routes.check_database", return_value=(True, "Healthy")), \
            patch("app.api.health.routes.check_redis", return_value=(False, "Redis Error")):
        response = client.get("/api/health")
        assert response.status_code == 503
        data = response.json
        assert data["status"] == "unhealthy"
        assert data["services"]["redis"]["status"] == "unhealthy"
        assert data["services"]["redis"]["message"] == "Redis Error"


def test_extended_health_check(client):
    """Test extended health check endpoint"""
    # Mock necessary components
    with patch("app.api.health.routes.check_database", return_value=(True, "Healthy")), \
            patch("app.api.health.routes.check_redis", return_value=(True, "Healthy")), \
            patch("psutil.Process") as mock_process:
        # Mock memory info
        mock_memory = MagicMock()
        mock_memory.rss = 1024 * 1024 * 100  # 100 MB
        mock_memory.vms = 1024 * 1024 * 200  # 200 MB
        mock_process.return_value.memory_info.return_value = mock_memory

        response = client.get("/api/health/extended")
        assert response.status_code == 200
        data = response.json

        assert data["status"] == "healthy"
        assert "system" in data
        assert "memory_usage" in data["system"]
        assert "services" in data
        assert data["services"]["database"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "healthy"


def test_extended_health_check_with_failure(client):
    """Test extended health check with service failure"""
    with patch("app.api.health.routes.check_database", return_value=(False, "DB Error")), \
            patch("app.api.health.routes.check_redis", return_value=(True, "Healthy")), \
            patch("psutil.Process") as mock_process:
        mock_memory = MagicMock()
        mock_memory.rss = 1024 * 1024 * 100
        mock_memory.vms = 1024 * 1024 * 200
        mock_process.return_value.memory_info.return_value = mock_memory

        response = client.get("/api/health/extended")
        assert response.status_code == 503
        data = response.json
        assert data["status"] == "unhealthy"
        assert data["services"]["database"]["status"] == "unhealthy"