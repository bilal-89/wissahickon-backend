# app/core/rate_limit.py

from functools import wraps
from flask import request, jsonify, current_app, g
import redis
from typing import Optional, Callable


class RateLimiter:
    """Rate limiter with graceful fallback for testing environments"""

    def __init__(self, redis_url: Optional[str] = None, app=None):
        self.redis_url = redis_url
        self.redis = None
        self.enabled = True  # Can be disabled for testing
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask application"""
        self.enabled = app.config.get('RATE_LIMIT_ENABLED', True)
        if not self.enabled:
            return

        try:
            self.redis_url = self.redis_url or app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            self.redis = redis.from_url(self.redis_url)
        except (redis.RedisError, KeyError):
            current_app.logger.warning("Redis not available - rate limiting disabled")
            self.enabled = False

    def limit(self, key_prefix: str, limit: int = 100, period: int = 60) -> Callable:
        """Rate limiting decorator with testing support"""

        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def wrapped(*args, **kwargs):
                # Skip rate limiting if disabled or Redis unavailable
                if not self.enabled or not self.redis:
                    return f(*args, **kwargs)

                try:
                    # Rest of your rate limiting logic remains the same...
                    redis_client = self.redis
                    identifier = request.remote_addr
                    if hasattr(g, 'tenant'):
                        identifier = f"{identifier}:{g.tenant.id}"

                    key = f"rate_limit:{key_prefix}:{identifier}"
                    current = redis_client.incr(key)

                    if current == 1:
                        redis_client.expire(key, period)

                    if current > limit:
                        response = jsonify({
                            'error': 'Rate limit exceeded',
                            'retry_after': redis_client.ttl(key)
                        })
                        response.headers['Retry-After'] = str(redis_client.ttl(key))
                        return response, 429

                    response = f(*args, **kwargs)

                    if isinstance(response, tuple):
                        response_obj, status_code = response
                    else:
                        response_obj, status_code = response, 200

                    if not hasattr(response_obj, 'headers'):
                        response_obj = jsonify(response_obj)

                    remaining = max(0, limit - current)
                    response_obj.headers.update({
                        'X-RateLimit-Limit': str(limit),
                        'X-RateLimit-Remaining': str(remaining),
                        'X-RateLimit-Reset': str(redis_client.ttl(key))
                    })

                    return response_obj, status_code

                except (redis.RedisError, Exception) as e:
                    # Log the error but don't break the request
                    current_app.logger.warning(f"Rate limiting error: {str(e)}")
                    return f(*args, **kwargs)

            return wrapped

        return decorator