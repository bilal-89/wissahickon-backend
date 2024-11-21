# app/__init__.py
from flask import Flask
from flask_migrate import Migrate
from .extensions import db
from .config import config_by_name


def create_app(config_name='development'):
    app = Flask(__name__)

    # Load config
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions
    db.init_app(app)

    # Initialize migrations
    migrate = Migrate(app, db)

    # Register blueprints (we'll add auth_bp later)
    # from .api.auth.routes import auth_bp
    # app.register_blueprint(auth_bp, url_prefix='/api/auth')

    return app