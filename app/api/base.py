from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

base_bp = Blueprint('base', __name__)

@base_bp.route('/health')
def health_check():
    return jsonify({'status': 'healthy'})

@base_bp.route('/protected')
@jwt_required()
def protected():
    return jsonify({'message': 'This is a protected endpoint'})