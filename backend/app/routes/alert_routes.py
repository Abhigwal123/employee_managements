# Alert Routes
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import User
import logging

logger = logging.getLogger(__name__)

alert_bp = Blueprint('alerts', __name__)

def get_current_user():
    """Get current authenticated user"""
    current_user_id = get_jwt_identity()
    return User.query.get(current_user_id)

@alert_bp.route('/', methods=['GET'])
@alert_bp.route('', methods=['GET'])
@jwt_required()
def get_alerts():
    """Get alerts for current tenant/user"""
    # Handle CORS preflight
    try:
        user = get_current_user()
        if not user:
            response = jsonify({'error': 'User not found'})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404
        
        # Parse query parameters
        status = request.args.get('status', None)
        page = int(request.args.get('page', 1) or 1)
        per_page = min(int(request.args.get('per_page', 20) or 20), 100)
        
        # For now, return empty alerts array
        # In the future, this would query from an Alert model/table
        alerts = []
        
        # Filter by status if provided
        if status:
            # In a real implementation, filter alerts by status
            pass
        
        response = jsonify({
            'success': True,
            'data': alerts,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': len(alerts),
                'pages': 1 if len(alerts) == 0 else 1,
                'has_next': False,
                'has_prev': False,
            }
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
    except Exception as e:
        logger.error(f"Get alerts error: {str(e)}")
        response = jsonify({'error': 'Failed to retrieve alerts', 'details': str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


