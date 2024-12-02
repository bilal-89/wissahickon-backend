import os
from datetime import timedelta
from google.cloud import secretmanager
import logging
from logging.handlers import RotatingFileHandler
import sys


# Enhanced logging setup
def setup_logging(app_env):
    """Configure logging based on environment"""
    log_level = logging.DEBUG if app_env == "development" else logging.INFO

    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Create custom formatter with tenant support
    class TenantFormatter(logging.Formatter):
        def format(self, record):
            if not hasattr(record, "tenant_id"):
                record.tenant_id = "NO_TENANT"
            return super().format(record)

    # Configure logging format
    log_format = TenantFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(tenant_id)s] - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)

    # File handler
    file_handler = RotatingFileHandler(
        "logs/app.log", maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
    )
    file_handler.setFormatter(log_format)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicates
    root_logger.handlers = []

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger


# Initialize logging
logger = setup_logging(os.getenv("FLASK_ENV", "development"))


def get_secret(secret_id, default_value):
    """Get secret from Secret Manager or return default value"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/wissahickon-dev/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.warning(f"Could not load secret {secret_id}: {e}")
        return default_value


def get_db_url(db_name):
    """Get database URL with connection parameters"""
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "PostgresDev2024!")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5433")

    # Add SSL mode for production
    ssl_mode = "?sslmode=verify-full" if os.getenv("FLASK_ENV") == "production" else ""

    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}{ssl_mode}"


class BaseConfig:
    """Base configuration with shared settings"""

    # Basic configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False  # Better performance
    PROPAGATE_EXCEPTIONS = True

    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)

    # CORS settings
    CORS_ENABLED = True
    CORS_SUPPORTS_CREDENTIALS = True

    # JWT settings
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_CSRF_PROTECT = True

    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STRATEGY = "fixed-window"

    # Database settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "max_overflow": 20,
    }

    # Secrets
    SECRET_KEY = get_secret("wis-flask-secret-key", os.getenv("SECRET_KEY", "dev-secret-key"))
    JWT_SECRET_KEY = get_secret(
        "wis-jwt-secret-key", os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key")
    )


class DevelopmentConfig(BaseConfig):
    """Development configuration"""

    DEBUG = True
    DEVELOPMENT = True

    # Database
    SQLALCHEMY_DATABASE_URI = get_db_url("wis_dev")
    SQLALCHEMY_ECHO = True

    # Rate limiting
    RATELIMIT_STORAGE_URL = "redis://localhost:6379"
    RATELIMIT_DEFAULT = "200 per day"

    # Security - relaxed for development
    SESSION_COOKIE_SECURE = False
    JWT_COOKIE_SECURE = False

    # CORS - relaxed for development
    CORS_ORIGINS = ["http://localhost:3000"]

    # Caching
    CACHE_TYPE = "simple"
    CACHE_DEFAULT_TIMEOUT = 300

    REDIS_URL = "redis://localhost:6379"

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,  # Base number of connections
        "max_overflow": 10,  # Additional connections if needed
        "pool_timeout": 30,  # Seconds to wait for connection
        "pool_recycle": 1800,  # Recycle connections after 30 min
        "pool_pre_ping": True,  # Check connection validity before use
    }


class ProductionConfig(BaseConfig):
    """Production configuration"""

    DEBUG = False
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_ECHO = False

    # Rate limiting
    RATELIMIT_STORAGE_URL = os.getenv("REDIS_URL")
    RATELIMIT_DEFAULT = "100 per day"
    RATELIMIT_HEADERS_ENABLED = True

    # Security
    SESSION_COOKIE_SECURE = True
    JWT_COOKIE_SECURE = True

    # CORS
    CORS_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")

    # Caching
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = os.getenv("REDIS_URL")
    CACHE_DEFAULT_TIMEOUT = 300

    # Monitoring
    SENTRY_DSN = get_secret("sentry-dsn", os.getenv("SENTRY_DSN"))

    # Performance
    PREFERRED_URL_SCHEME = "https"

    # File uploads
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    REDIS_URL = os.getenv("REDIS_URL")


class TestingConfig(BaseConfig):
    """Testing configuration"""

    TESTING = True
    DEBUG = False

    # Database
    SQLALCHEMY_DATABASE_URI = get_db_url("app_test")
    SQLALCHEMY_ECHO = False

    # Security - disabled for testing
    WTF_CSRF_ENABLED = False
    JWT_COOKIE_CSRF_PROTECT = False

    # Rate limiting
    RATELIMIT_ENABLED = False

    # Caching
    CACHE_TYPE = "null"

    # Make testing faster
    HASH_ROUNDS = 1


def configure_app(app):
    """Configure the Flask app with additional settings"""
    env = os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_by_name[env])

    # Additional production configurations
    if env == "production":
        # Configure Sentry
        if app.config.get("SENTRY_DSN"):
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration

            sentry_sdk.init(
                dsn=app.config["SENTRY_DSN"],
                integrations=[FlaskIntegration()],
                traces_sample_rate=1.0,
                environment=env,
            )

        # Configure SSL if behind proxy
        if os.getenv("BEHIND_PROXY", False):
            from werkzeug.middleware.proxy_fix import ProxyFix

            app.wsgi_app = ProxyFix(
                app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1
            )

    return app


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    """Get configuration based on environment"""
    env = os.getenv("FLASK_ENV", "development")
    return config_by_name[env]
