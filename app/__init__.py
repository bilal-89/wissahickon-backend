# app/__init__.py
from flask import Flask
from .extensions import db, migrate, cors, jwt
from .config import get_config


def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)
    jwt.init_app(app)

    # Register base blueprint
    from .api.base import base_bp
    app.register_blueprint(base_bp, url_prefix='/api')

    return app