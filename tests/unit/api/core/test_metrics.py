# tests/unit/api/core/test_metrics.py
import pytest
from app.core.metrics import metrics, track_performance, capture_error
from flask import Blueprint, jsonify, Flask
from werkzeug.exceptions import NotFound
import time
from app.extensions import db


@pytest.fixture
def test_app():
    """Create a fresh test application for each test"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    return app


def test_basic_metrics_tracking(test_app):
    """Test basic metrics tracking functionality"""
    # Create test blueprint with tracked endpoint
    bp = Blueprint('test_metrics', __name__)

    @bp.route('/test-metrics')
    @track_performance
    def test_metrics_endpoint():
        return jsonify({'status': 'ok'})

    # Register blueprint
    test_app.register_blueprint(bp)

    # Reset metrics
    metrics.request_count = 0
    metrics.error_count = 0
    metrics.response_times = {}
    metrics.last_errors = {}

    with test_app.app_context():
        with test_app.test_client() as client:
            response = client.get('/test-metrics')
            assert response.status_code == 200

            stats = metrics.get_stats()
            assert stats['total_requests'] > 0
            assert 'test_metrics_endpoint' in str(stats['endpoints'])
            assert stats['error_count'] == 0


def test_error_tracking(test_app):
    """Test error tracking functionality"""
    # Create test blueprint with tracked endpoint
    bp = Blueprint('test_error', __name__)

    @bp.route('/test-error')
    @track_performance
    @capture_error
    def error_endpoint():
        raise ValueError("Test error")

    # Register blueprint
    test_app.register_blueprint(bp)

    # Reset metrics
    metrics.request_count = 0
    metrics.error_count = 0
    metrics.response_times = {}
    metrics.last_errors = {}

    with test_app.app_context():
        with test_app.test_client() as client:
            response = client.get('/test-error')
            assert response.status_code == 500

            stats = metrics.get_stats()
            assert stats['error_count'] > 0
            assert len(metrics.last_errors) > 0


def test_performance_tracking(test_app):
    """Test the performance tracking decorator"""
    # Create test blueprint with tracked endpoint
    bp = Blueprint('test_perf', __name__)

    @bp.route('/test-perf')
    @track_performance
    def test_endpoint():
        time.sleep(0.1)  # Simulate some work
        return jsonify({'status': 'ok'})

    # Register blueprint
    test_app.register_blueprint(bp)

    # Reset metrics
    metrics.request_count = 0
    metrics.response_times = {}

    with test_app.app_context():
        with test_app.test_client() as client:
            response = client.get('/test-perf')
            assert response.status_code == 200

            stats = metrics.get_stats()
            assert 'test_endpoint' in str(stats['endpoints'])
            endpoint_stats = next((v for k, v in stats['endpoints'].items()
                                   if 'test_endpoint' in k), None)
            assert endpoint_stats is not None
            assert float(endpoint_stats['average_response_time'].replace('s', '')) >= 0.1