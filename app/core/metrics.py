# app/core/metrics.py
from functools import wraps
from time import time
from flask import request, g, current_app, jsonify
import logging
from typing import Dict, Any, Callable
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


class Metrics:
    """Track application metrics"""

    def __init__(self):
        self._lock = Lock()
        self.request_count = 0
        self.error_count = 0
        self.response_times: Dict[str, list] = {}
        self.last_errors: Dict[str, Any] = {}

    def track_request(self, endpoint: str, duration: float, status_code: int):
        """Track request metrics with thread safety"""
        with self._lock:
            self.request_count += 1

            if endpoint not in self.response_times:
                self.response_times[endpoint] = []
            self.response_times[endpoint].append(duration)

            if status_code >= 400:
                self.error_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics with thread safety"""
        with self._lock:
            stats = {
                "total_requests": self.request_count,
                "error_count": self.error_count,
                "error_rate": (
                    (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
                ),
                "endpoints": {},
            }

            for endpoint, times in self.response_times.items():
                if times:
                    avg_time = sum(times) / len(times)
                    stats["endpoints"][endpoint] = {
                        "average_response_time": f"{avg_time:.3f}s",
                        "request_count": len(times),
                    }

            return stats

    def reset(self):
        """Reset all metrics - useful for testing"""
        with self._lock:
            self.request_count = 0
            self.error_count = 0
            self.response_times = {}
            self.last_errors = {}

    def add_error(self, error_id: str, error_details: Dict[str, Any]):
        """Add error details with thread safety"""
        with self._lock:
            self.last_errors[error_id] = error_details
            self.error_count += 1


# Global metrics instance
metrics = Metrics()


def capture_error(f: Callable):
    """Decorator to capture and track errors"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Log error details
            error_id = str(time())
            tenant_id = getattr(g, "tenant", None)
            error_details = {
                "error_id": error_id,
                "timestamp": datetime.utcnow().isoformat(),
                "endpoint": request.endpoint,
                "method": request.method,
                "tenant_id": tenant_id.id if tenant_id else None,
                "error": str(e),
                "error_type": type(e).__name__,
            }

            # Track in metrics using thread-safe method
            metrics.add_error(error_id, error_details)

            # Log error
            current_app.logger.exception(f"Unhandled Exception: {str(e)}")

            # Return error response
            return jsonify({"error": str(e), "error_id": error_id}), 500

    return decorated_function


def track_performance(f: Callable):
    """Decorator to track endpoint performance"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time()

        try:
            response = f(*args, **kwargs)
            duration = time() - start_time

            # Handle tuple responses (typical in error cases)
            if isinstance(response, tuple):
                response_obj = response[0]
                status = response[1]
            else:
                response_obj = response
                status = response.status_code

            # Track metrics
            metrics.track_request(endpoint=request.endpoint, duration=duration, status_code=status)

            return response

        except Exception as e:
            duration = time() - start_time
            metrics.track_request(endpoint=request.endpoint, duration=duration, status_code=500)
            raise

    return decorated_function


def get_current_metrics():
    """Get current application metrics"""
    return metrics.get_stats()
