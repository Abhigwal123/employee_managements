# Role Routes
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import logging

logger = logging.getLogger(__name__)

role_bp = Blueprint('roles', __name__)

# Default role configurations
DEFAULT_ROLES = [
    {
        'role': 'ScheduleManager',
        'label': '排班主管',
        'badge': {'bg': 'bg-blue-100', 'text': 'text-blue-800'},
    },
    {
        'role': 'Schedule_Manager',
        'label': '排班主管',
        'badge': {'bg': 'bg-blue-100', 'text': 'text-blue-800'},
    },
    {
        'role': 'Employee',
        'label': '部門員工',
        'badge': {'bg': 'bg-gray-100', 'text': 'text-gray-800'},
    },
    {
        'role': 'ClientAdmin',
        'label': '客戶管理員',
        'badge': {'bg': 'bg-purple-100', 'text': 'text-purple-800'},
    },
    {
        'role': 'Client_Admin',
        'label': '客戶管理員',
        'badge': {'bg': 'bg-purple-100', 'text': 'text-purple-800'},
    },
]

@role_bp.route('/', methods=['GET'])
@role_bp.route('', methods=['GET'])
@jwt_required()
def get_roles():
    """Get all available roles with their configurations"""
    # Handle CORS preflight
    try:
        # Return default roles for now
        # In the future, this could fetch from a database table
        response = jsonify({
            'success': True,
            'data': DEFAULT_ROLES,
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
    except Exception as e:
        logger.error(f"Get roles error: {str(e)}")
        response = jsonify({'error': 'Failed to retrieve roles', 'details': str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


