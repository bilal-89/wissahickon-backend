# tests/unit/api/core/test_rate_limiter.py

import pytest
from flask import Flask, jsonify
import fakeredis
from app.core.rate_limiter import RateLimiter


class TestRateLimiter:
    @pytest.fixture
    def fake_redis(self):
        """Create a shared fake Redis instance for all tests"""
        return fakeredis.FakeStrictRedis()

    @pytest.fixture
    def app(self, fake_redis):
        """Create test Flask app with rate limiter"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['REDIS_URL'] = 'redis://localhost:6379/0'

        # Create and initialize limiter with our fake redis
        limiter = RateLimiter(redis_url='redis://fake')
        limiter.init_app(app)  # This will store limiter on app
        limiter.redis = fake_redis  # Use our shared fake Redis

        # Add test endpoint
        @app.route('/test')
        @limiter.limit('test', limit=2, period=5)
        def test_endpoint():
            return jsonify({'status': 'success'})

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client with app context"""
        with app.test_client() as client:
            with app.app_context():
                yield client

    def test_within_limit(self, client, fake_redis):
        """Test requests within rate limit"""
        # First request
        response = client.get('/test')
        assert response.status_code == 200
        assert 'X-RateLimit-Remaining' in response.headers
        assert int(response.headers['X-RateLimit-Remaining']) == 1

        # Second request
        response = client.get('/test')
        assert response.status_code == 200
        assert int(response.headers['X-RateLimit-Remaining']) == 0

    def test_exceeds_limit(self, client, fake_redis):
        """Test requests exceeding rate limit"""
        # Clear any previous state
        fake_redis.flushall()

        # Make requests up to limit
        for _ in range(2):
            client.get('/test')

        # Third request should fail
        response = client.get('/test')
        assert response.status_code == 429
        assert b'Rate limit exceeded' in response.data
        assert 'Retry-After' in response.headers

    def test_limit_reset(self, client, app, fake_redis):
        """Test rate limit reset after period"""
        # Make initial request
        response = client.get('/test')
        assert response.status_code == 200

        # Clear Redis to simulate time passing
        fake_redis.flushall()

        # Should work again
        response = client.get('/test')
        assert response.status_code == 200
        assert int(response.headers['X-RateLimit-Remaining']) == 1

    def test_rate_limit_headers(self, client, fake_redis):
        """Test rate limit headers"""
        # Clear any previous state
        fake_redis.flushall()

        response = client.get('/test')
        headers = response.headers

        assert 'X-RateLimit-Limit' in headers
        assert 'X-RateLimit-Remaining' in headers
        assert 'X-RateLimit-Reset' in headers

        assert headers['X-RateLimit-Limit'] == '2'
        assert headers['X-RateLimit-Remaining'] == '1'