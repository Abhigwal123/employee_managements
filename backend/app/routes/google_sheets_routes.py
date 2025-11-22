"""
Google Sheets API Routes
Provides endpoints for listing, validating, and fetching Google Sheets data
"""
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User, ScheduleDefinition
import sys
import os

# Add project root to path for importing app.services.google_sheets
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Use shared import utility
from app.services.google_sheets_import import (
    _try_import_google_sheets,
    SHEETS_AVAILABLE as GOOGLE_SHEETS_AVAILABLE,
    GoogleSheetsService,
    list_sheets,
    validate_sheets,
    fetch_schedule_data
)

# Try import at module load
import logging
logger = logging.getLogger(__name__)
success, path = _try_import_google_sheets()
if success:
    logger.info(f"✅ Google Sheets routes: Service loaded from {path}")
else:
    logger.warning("⚠️ Google Sheets routes: Service not available")

google_sheets_bp = Blueprint('google_sheets', __name__)


def get_current_user():
    """Get current authenticated user"""
    current_user_id = get_jwt_identity()
    return User.query.get(current_user_id)


@google_sheets_bp.route('/list', methods=['GET', 'POST'])
@jwt_required()
def list_sheets_endpoint():
    """
    List all sheets in a spreadsheet
    
    POST body or GET params:
        spreadsheet_url: URL of the spreadsheet
    """
    if not GOOGLE_SHEETS_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Google Sheets service not available"
        }), 503
    
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get spreadsheet URL from request
        if request.method == 'POST':
            data = request.get_json() or {}
            spreadsheet_url = data.get('spreadsheet_url')
        else:
            spreadsheet_url = request.args.get('spreadsheet_url')
        
        if not spreadsheet_url:
            return jsonify({'error': 'spreadsheet_url is required'}), 400
        
        # Get credentials path from config
        creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
        
        # List sheets
        result = list_sheets(spreadsheet_url, creds_path)
        
        if result.get("success"):
            return jsonify({
                "success": True,
                "count": result.get("count", 0),
                "sheets": result.get("sheets", []),
                "spreadsheet_title": result.get("spreadsheet_title")
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error")
            }), 400
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error listing sheets: {e}")
        return jsonify({'error': 'Failed to list sheets', 'details': str(e)}), 500


@google_sheets_bp.route('/validate', methods=['POST'])
@jwt_required()
def validate_sheets_endpoint():
    """
    Validate Parameters and Preschedule sheets
    
    POST body:
        params_url: URL of Parameters sheet (required)
        preschedule_url: URL of Preschedule sheet (optional)
    """
    if not GOOGLE_SHEETS_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Google Sheets service not available"
        }), 503
    
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        params_url = data.get('params_url') or data.get('paramsSheetURL')
        preschedule_url = data.get('preschedule_url') or data.get('prescheduleSheetURL')
        
        if not params_url:
            return jsonify({'error': 'params_url is required'}), 400
        
        # Get credentials path from config
        creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
        
        # Validate sheets
        result = validate_sheets(params_url, preschedule_url, creds_path)
        
        return jsonify(result), 200 if result.get("success") else 400
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error validating sheets: {e}")
        return jsonify({'error': 'Failed to validate sheets', 'details': str(e)}), 500


@google_sheets_bp.route('/fetch/<schedule_def_id>', methods=['GET'])
@jwt_required()
def fetch_schedule_data_endpoint(schedule_def_id):
    """
    Fetch all schedule data for a schedule definition (all 6 sheets)
    
    GET /api/v1/sheets/fetch/<schedule_def_id>
    
    Returns all 6 sheets:
    - Parameters
    - Employee
    - Preferences
    - Pre-Schedule
    - Designation Flow
    - Final Output
    
    Data is filtered based on user role.
    """
    if not GOOGLE_SHEETS_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Google Sheets service not available"
        }), 503
    
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find schedule definition
        schedule_def = ScheduleDefinition.query.get(schedule_def_id)
        if not schedule_def:
            return jsonify({'error': 'Schedule definition not found'}), 404
        
        # Check tenant access
        if user.tenantID != schedule_def.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get credentials path from config
        creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
        
        # Get user role for filtering
        user_role = user.role if user else None
        
        # Get month from query parameter if provided
        month = request.args.get('month') if request else None
        
        # Fetch schedule data (all 6 sheets) with caching
        result = fetch_schedule_data(schedule_def_id, creds_path, user_role=user_role, month=month)
        
        return jsonify(result), 200 if result.get("success") else 400
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching schedule data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Failed to fetch schedule data', 'details': str(e)}), 500
