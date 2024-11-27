# app/__init__.py
from flask import Flask, jsonify, request
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from .extensions import db
from .config import config_by_name
from .core.errors import APIError
from .core.exceptions import PermissionDenied  # Add this import
from .api.tenant import tenant_bp
from .api.auth.routes import auth_bp
from .api.user import user_bp
from .api.settings.routes import settings_bp
from app.api.health.routes import health_bp
from app.core.monitoring import init_sentry


import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name='development'):
    app = Flask(__name__)

    # Load config
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    CORS(app)

    init_sentry(app)



    # Initialize migrations
    migrate = Migrate(app, db)

    # Debug routes endpoint
    @app.route('/debug/routes')
    def list_routes():
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'path': str(rule)
            })
        return jsonify(routes)

    # Root endpoint
    @app.route('/')
    def root():
        return jsonify({
            'service': 'Wissahickon Backend API',
            'version': '1.0.0',
            'status': 'running'
        })

    # Register error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        logger.error(f"404 Error: {request.url}")
        return jsonify({
            'error': 'Not Found',
            'message': f"The requested URL {request.path} was not found"
        }), 404

    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.error(f"Unhandled Exception: {str(error)}", exc_info=True)
        return jsonify({
            'error': str(error.__class__.__name__),
            'message': str(error)
        }), 500

    @app.errorhandler(APIError)
    def handle_api_error(error):
        logger.error(f"API Error: {str(error)}")
        return jsonify({
            'error': 'API Error',
            'message': str(error)
        }), error.status_code

    @app.errorhandler(PermissionDenied)  # Add this handler
    def handle_permission_denied(error):
        logger.error(f"Permission Denied: {str(error)}")
        return jsonify({
            'error': 'Permission Denied',
            'message': str(error)
        }), 403

    # Request logging
    @app.before_request
    def log_request_info():
        logger.info(f"Request Method: {request.method}")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Request Headers: {dict(request.headers)}")
        if request.is_json:
            logger.info(f"Request Body: {request.get_json(silent=True)}")

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(tenant_bp, url_prefix='/api/tenants')
    app.register_blueprint(user_bp, url_prefix='/api/users')  # Add this line
    app.register_blueprint(settings_bp, url_prefix='/api/settings')  # Add this line
    app.register_blueprint(health_bp, url_prefix='/api')
    # Log registered routes
    logger.info("Registered routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"{rule.endpoint}: {rule.methods} {rule.rule}")

    return app