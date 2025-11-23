from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from ..utils.auth import role_required
from .. import db
from ..models import Department, User
from ..utils.security import sanitize_input
import logging

logger = logging.getLogger(__name__)


# Note: url_prefix set to None - will be set during registration in __init__.py
clientadmin_bp = Blueprint("clientadmin", __name__)


@clientadmin_bp.route("/dashboard", methods=["GET"])
@role_required("ClientAdmin")
def dashboard():
    """Client Admin dashboard with Tenant, Department, User Account, and Permissions views"""
    import logging
    trace_logger = logging.getLogger('trace')
    
    trace_logger.info("[TRACE] Backend: GET /clientadmin/dashboard")
    
    from flask_jwt_extended import get_jwt_identity, get_jwt
    from app.models import User, Tenant, Department
    
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            response = jsonify({"success": False, "error": "User not found"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404
        
        tenant = user.tenant
        if not tenant:
            response = jsonify({"success": False, "error": "Tenant not found"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404
        
        # Get tenant statistics
        stats = {
            "tenants": 1,  # Current tenant only
            "departments": tenant.departments.count(),
            "users": tenant.users.count(),
            "active_users": tenant.users.filter_by(status='active').count()
        }
        
        response = jsonify({
            "success": True,
            "dashboard": "clientadmin",
            "user": user.to_dict(),
            "tenant": tenant.to_dict(),
            "stats": stats,
            "views": ["C1: Tenant", "C2: Department", "C3: User Account", "C4: Permissions"]
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in clientadmin dashboard: {e}")
        import traceback
        logger.error(traceback.format_exc())
        response = jsonify({"success": False, "error": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


@clientadmin_bp.route("/departments", methods=["GET"])
@role_required("ClientAdmin")
def departments():
    return jsonify({"departments": []})


@clientadmin_bp.route("/department", methods=["POST"])
@role_required("ClientAdmin")
def create_department():
    """Create a new department (ClientAdmin only)"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            response = jsonify({"error": "User not found"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404
        
        # Check if user is ClientAdmin (platform admin)
        if not user.is_client_admin:
            response = jsonify({"error": "Access denied"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 403
        
        data = request.get_json()
        if not data:
            response = jsonify({"error": "No data provided"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400
        
        # Validate department name
        department_name = data.get("name") or data.get("departmentName")
        if not department_name:
            response = jsonify({"error": "Department name required"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400
        
        # Sanitize input
        department_name = sanitize_input(department_name)
        
        # Check if department name already exists in tenant
        existing_dept = Department.find_by_name(user.tenantID, department_name)
        if existing_dept:
            response = jsonify({"error": "Department with this name already exists"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 409
        
        # Create department
        department = Department(
            tenantID=user.tenantID,
            departmentName=department_name,
            description=data.get("description"),
            is_active=data.get("is_active", True)
        )
        
        db.session.add(department)
        db.session.commit()
        
        logger.info(f"New department created: {department.departmentName} by user: {user.username}")
        
        response = jsonify({
            "success": True,
            "message": "Department created successfully",
            "department": department.to_dict()
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create department error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        response = jsonify({"error": "Failed to create department", "details": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


@clientadmin_bp.route("/department/<int:dept_id>", methods=["PUT"])
@role_required("ClientAdmin")
def update_department(dept_id: int):
    return jsonify({"updated": True, "id": dept_id})


@clientadmin_bp.route("/users", methods=["GET"])
@role_required("ClientAdmin")
def users():
    return jsonify({"users": []})


@clientadmin_bp.route("/user", methods=["POST"])
@role_required("ClientAdmin")
def create_user():
    return jsonify({"created": True}), 201


@clientadmin_bp.route("/user/<int:user_id>", methods=["PUT"])
@role_required("ClientAdmin")
def update_user(user_id: int):
    return jsonify({"updated": True, "id": user_id})


@clientadmin_bp.route("/schedule/access", methods=["PUT"])
@role_required("ClientAdmin")
def update_schedule_access():
    return jsonify({"access_updated": True})


@clientadmin_bp.route("/c1-tenant", methods=["GET"])
@role_required("ClientAdmin")
def c1_tenant():
    """C1 Tenant Dashboard - Tenant overview"""
    from flask_jwt_extended import get_jwt_identity
    from app.services.dashboard_data_service import DashboardDataService
    
    try:
        current_user_id = get_jwt_identity()
        service = DashboardDataService()
        dashboard_data = service.get_clientadmin_c1_data(current_user_id)
        
        if dashboard_data.get("success"):
            return jsonify(dashboard_data), 200
        else:
            return jsonify(dashboard_data), 400
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in C1 dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@clientadmin_bp.route("/c2-department", methods=["GET"])
@role_required("ClientAdmin")
def c2_department():
    """C2 Department Management Dashboard"""
    from flask_jwt_extended import get_jwt_identity
    from app.services.dashboard_data_service import DashboardDataService
    
    try:
        current_user_id = get_jwt_identity()
        service = DashboardDataService()
        dashboard_data = service.get_clientadmin_c2_data(current_user_id)
        
        if dashboard_data.get("success"):
            return jsonify(dashboard_data), 200
        else:
            return jsonify(dashboard_data), 400
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in C2 dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@clientadmin_bp.route("/c3-user-account", methods=["GET"])
@role_required("ClientAdmin")
def c3_user_account():
    """C3 User Account Management Dashboard"""
    from flask_jwt_extended import get_jwt_identity
    from app.services.dashboard_data_service import DashboardDataService
    
    try:
        current_user_id = get_jwt_identity()
        service = DashboardDataService()
        dashboard_data = service.get_clientadmin_c3_data(current_user_id)
        
        if dashboard_data.get("success"):
            return jsonify(dashboard_data), 200
        else:
            return jsonify(dashboard_data), 400
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in C3 dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@clientadmin_bp.route("/c4-permissions", methods=["GET"])
@role_required("ClientAdmin")
def c4_permissions():
    """C4 Permission Maintenance Dashboard - Includes Designation Flow from Google Sheets"""
    from flask_jwt_extended import get_jwt_identity
    from flask import current_app
    from app.services.dashboard_data_service import DashboardDataService
    from app.models import ScheduleDefinition
    
    try:
        current_user_id = get_jwt_identity()
        from app.models import User
        user = User.query.get(current_user_id)
        
        # Get designation flow data from sheets if available
        designation_flow_data = None
        schedule_def = ScheduleDefinition.query.filter_by(
            tenantID=user.tenantID,
            is_active=True
        ).first()
        
        if schedule_def:
            creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
            from app.services.google_sheets.service import fetch_schedule_data
            sheets_data = fetch_schedule_data(
                schedule_def.scheduleDefID,
                creds_path,
                user_role="clientadmin"
            )
            if sheets_data.get("success"):
                designation_flow_data = sheets_data.get("sheets", {}).get("designation_flow", {})
        
        # Get permissions from database
        service = DashboardDataService()
        dashboard_data = service.get_clientadmin_c4_data(current_user_id)
        
        # Add designation flow data
        if designation_flow_data:
            dashboard_data["data"]["designation_flow"] = {
                "rows": designation_flow_data.get("data", []),
                "columns": designation_flow_data.get("columns", [])
            }
        
        if dashboard_data.get("success"):
            return jsonify(dashboard_data), 200
        else:
            return jsonify(dashboard_data), 400
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in C4 dashboard: {e}")
        return jsonify({"error": str(e)}), 500



