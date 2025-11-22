# Department Routes
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Department, User
try:
    from app.schemas import DepartmentSchema, DepartmentUpdateSchema, PaginationSchema
    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False
    DepartmentSchema = None
    DepartmentUpdateSchema = None
    PaginationSchema = None
from app.utils.security import sanitize_input
from app.utils.role_utils import is_client_admin_role, is_schedule_manager_role
from app.utils.tenant_filter import get_tenant_filtered_query
import logging

logger = logging.getLogger(__name__)

department_bp = Blueprint('departments', __name__)

def get_current_user():
    """Get current authenticated user"""
    current_user_id = get_jwt_identity()
    return User.query.get(current_user_id)

def require_admin_or_scheduler():
    """Decorator to require admin or scheduler role"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Admin or scheduler access required'}), 403
            if not (
                is_client_admin_role(user.role)
                or is_schedule_manager_role(user.role)
                or user.role in ['admin', 'scheduler']
            ):
                return jsonify({'error': 'Admin or scheduler access required'}), 403
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

@department_bp.route('/', methods=['GET'])
@department_bp.route('', methods=['GET'])  # Support both / and no slash
@jwt_required()
def get_departments():
    """Get departments for current tenant (ClientAdmin can access all tenants)"""
    import logging
    trace_logger = logging.getLogger('trace')
    
    # [TRACE] Logging
    trace_logger.info(f"[TRACE] Backend: GET /departments")
    trace_logger.info(f"[TRACE] Backend: Path: {request.path}")
    trace_logger.info(f"[TRACE] Backend: Full path: {request.full_path}")
    trace_logger.info(f"[TRACE] Backend: Query params: {dict(request.args)}")
    
    try:
        from flask_jwt_extended import get_jwt_identity, get_jwt
        current_user_id = get_jwt_identity()
        claims = get_jwt() or {}
        trace_logger.info(f"[TRACE] Backend: User ID: {current_user_id}")
        trace_logger.info(f"[TRACE] Backend: Role: {claims.get('role')}")
    except:
        pass
    
    try:
        user = get_current_user()
        if not user:
            response = jsonify({'error': 'User not found'})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404
        
        # Parse pagination parameters with safe defaults
        try:
            if SCHEMAS_AVAILABLE and PaginationSchema:
                pagination_schema = PaginationSchema()
                pagination_data = pagination_schema.load(request.args)
                page = int(pagination_data.get('page', 1))
                per_page = min(int(pagination_data.get('per_page', 20)), 100)
            else:
                page = int(request.args.get('page', 1) or 1)
                per_page = min(int(request.args.get('per_page', 20) or 20), 100)
        except Exception:
            page = int(request.args.get('page', 1) or 1)
            per_page = min(int(request.args.get('per_page', 20) or 20), 100)
        
        # Query departments - ClientAdmin sees all, others see only their tenant
        departments_query = get_tenant_filtered_query(Department, user)
        
        # Apply active filter if specified
        active_filter = request.args.get('active')
        if active_filter is not None:
            is_active = active_filter.lower() == 'true'
            departments_query = departments_query.filter_by(is_active=is_active)
        
        departments_pagination = departments_query.order_by(Department.created_at.desc()).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        departments = [dept.to_dict() for dept in departments_pagination.items]
        
        import logging
        trace_logger = logging.getLogger('trace')
        trace_logger.info(f"[TRACE] Backend: Returning {len(departments)} departments")
        trace_logger.info(f"[TRACE] Backend: Response structure: {{success: True, data: [{len(departments)} items], pagination: {{...}}}}")
        
        response = jsonify({
            'success': True,
            'data': departments,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': departments_pagination.total,
                'pages': departments_pagination.pages,
                'has_next': departments_pagination.has_next,
                'has_prev': departments_pagination.has_prev
            }
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
        
    except Exception as e:
        logger.error(f"Get departments error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        response = jsonify({'error': 'Failed to retrieve departments', 'details': str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

@department_bp.route('/', methods=['POST'])
@jwt_required()
@require_admin_or_scheduler()
def create_department():
    """Create a new department"""
    try:
        current_user = get_current_user()
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate department data
        department_schema = DepartmentSchema()
        errors = department_schema.validate(data)
        if errors:
            return jsonify({'error': 'Invalid department data', 'details': errors}), 400
        
        # Sanitize input
        department_name = sanitize_input(data['departmentName'])
        
        # Check if department name already exists in tenant
        existing_dept = Department.find_by_name(current_user.tenantID, department_name)
        if existing_dept:
            return jsonify({'error': 'Department with this name already exists'}), 409
        
        # Create department
        department = Department(
            tenantID=current_user.tenantID,
            departmentName=department_name,
            description=data.get('description'),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(department)
        db.session.commit()
        
        logger.info(f"New department created: {department.departmentName} by user: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Department created successfully',
            'data': department.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create department error: {str(e)}")
        return jsonify({'error': 'Failed to create department', 'details': str(e)}), 500

@department_bp.route('/<department_id>', methods=['GET'])
@jwt_required()
def get_department(department_id):
    """Get specific department information"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find department
        department = Department.query.get(department_id)
        if not department:
            return jsonify({'error': 'Department not found'}), 404
        
        # Check tenant access
        if user.tenantID != department.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'data': department.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Get department error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve department', 'details': str(e)}), 500

@department_bp.route('/<department_id>', methods=['PUT'])
@jwt_required()
@require_admin_or_scheduler()
def update_department(department_id):
    """Update department information"""
    try:
        current_user = get_current_user()
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate update data
        update_schema = DepartmentUpdateSchema()
        errors = update_schema.validate(data)
        if errors:
            return jsonify({'error': 'Invalid update data', 'details': errors}), 400
        
        # Find department
        department = Department.query.get(department_id)
        if not department:
            return jsonify({'error': 'Department not found'}), 404
        
        # Check tenant access
        if current_user.tenantID != department.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update fields
        if 'departmentName' in data:
            department_name = sanitize_input(data['departmentName'])
            
            # Check if new name conflicts
            existing_dept = Department.find_by_name(current_user.tenantID, department_name)
            if existing_dept and existing_dept.departmentID != department_id:
                return jsonify({'error': 'Department with this name already exists'}), 409
            
            department.departmentName = department_name
        
        if 'description' in data:
            department.description = data['description']
        
        if 'is_active' in data:
            department.is_active = data['is_active']
        
        department.updated_at = db.func.now()
        db.session.commit()
        
        logger.info(f"Department updated: {department.departmentName} by user: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Department updated successfully',
            'data': department.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update department error: {str(e)}")
        return jsonify({'error': 'Failed to update department', 'details': str(e)}), 500

@department_bp.route('/<department_id>', methods=['DELETE'])
@jwt_required()
@require_admin_or_scheduler()
def delete_department(department_id):
    """Delete department (soft delete)"""
    try:
        current_user = get_current_user()
        
        # Find department
        department = Department.query.get(department_id)
        if not department:
            return jsonify({'error': 'Department not found'}), 404
        
        # Check tenant access
        if current_user.tenantID != department.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        # Soft delete (deactivate)
        department.is_active = False
        department.updated_at = db.func.now()
        db.session.commit()
        
        logger.info(f"Department deactivated: {department.departmentName} by user: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Department deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete department error: {str(e)}")
        return jsonify({'error': 'Failed to delete department', 'details': str(e)}), 500







