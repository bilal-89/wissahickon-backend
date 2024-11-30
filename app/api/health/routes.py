# app/api/health/routes.py

from flask import Blueprint, jsonify, current_app
from app.extensions import db
from redis import Redis
from sqlalchemy import text
import time
from app.core.metrics import track_performance, capture_error


health_bp = Blueprint('health', __name__)


def check_database():
    """Check database connection"""
    try:
        db.session.execute(text('SELECT 1'))
        return True, "Healthy"
    except Exception as e:
        return False, str(e)


def check_redis():
    """Check Redis connection"""
    try:
        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379')
        redis_client = Redis.from_url(redis_url)
        redis_client.ping()
        return True, "Healthy"
    except Exception as e:
        return False, str(e)


@health_bp.route('/health')
@track_performance
@capture_error
def health_check():
    """Basic health check endpoint"""
    start_time = time.time()

    # Check core services
    db_healthy, db_message = check_database()
    redis_healthy, redis_message = check_redis()

    # Calculate response time
    response_time = time.time() - start_time

    status = "healthy" if all([db_healthy, redis_healthy]) else "unhealthy"

    health_status = {
        "status": status,
        "response_time": f"{response_time:.3f}s",
        "services": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "message": db_message
            },
            "redis": {
                "status": "healthy" if redis_healthy else "unhealthy",
                "message": redis_message
            }
        },
        "version": current_app.config.get('VERSION', '1.0.0')
    }

    status_code = 200 if status == "healthy" else 503
    return jsonify(health_status), status_code


@health_bp.route('/health/extended')
def extended_health_check():
    """Detailed health check with additional metrics"""
    start_time = time.time()

    try:
        # Database checks
        db_start = time.time()
        db_healthy, db_message = check_database()
        db_time = time.time() - db_start

        # Redis checks
        redis_start = time.time()
        redis_healthy, redis_message = check_redis()
        redis_time = time.time() - redis_start

        # Memory usage
        import psutil
        memory = psutil.Process().memory_info()

        health_status = {
            "status": "healthy" if all([db_healthy, redis_healthy]) else "unhealthy",
            "response_time": f"{time.time() - start_time:.3f}s",
            "services": {
                "database": {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "response_time": f"{db_time:.3f}s",
                    "message": db_message
                },
                "redis": {
                    "status": "healthy" if redis_healthy else "unhealthy",
                    "response_time": f"{redis_time:.3f}s",
                    "message": redis_message
                }
            },
            "system": {
                "memory_usage": {
                    "rss": f"{memory.rss / 1024 / 1024:.2f}MB",
                    "vms": f"{memory.vms / 1024 / 1024:.2f}MB"
                }
            },
            "version": current_app.config.get('VERSION', '1.0.0')
        }

        status_code = 200 if health_status["status"] == "healthy" else 503
        return jsonify(health_status), status_code

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "response_time": f"{time.time() - start_time:.3f}s"
        }), 500