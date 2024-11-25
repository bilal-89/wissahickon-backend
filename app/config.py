# app/config.py
import os
from datetime import timedelta
from google.cloud import secretmanager
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', 'PostgresDev2024!')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

class BaseConfig:
    # Basic configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)

    # Secrets
    SECRET_KEY = get_secret('wis-flask-secret-key', os.getenv('SECRET_KEY', 'dev-secret-key'))
    JWT_SECRET_KEY = get_secret('wis-jwt-secret-key', os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-key'))


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = get_db_url('wis_dev')
    SQLALCHEMY_ECHO = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = get_db_url('app_test')
    SQLALCHEMY_ECHO = True
    WTF_CSRF_ENABLED = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name[env]