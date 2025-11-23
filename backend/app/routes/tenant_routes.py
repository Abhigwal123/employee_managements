# Tenant Routes
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Tenant, User
try:
    from ..schemas import TenantSchema, TenantUpdateSchema, PaginationSchema
    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False
    TenantSchema = None
    TenantUpdateSchema = None
    PaginationSchema = None
from ..utils.security import sanitize_input
from ..utils.role_utils import is_sys_admin_role
import logging

logger = logging.getLogger(__name__)

tenant_bp = Blueprint('tenants', __name__)

def get_current_user():
    """Get current authenticated user"""
    current_user_id = get_jwt_identity()
    return User.query.get(current_user_id)

def require_admin(allow_sysadmin: bool = False):
    """Decorator to require admin role"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Admin access required'}), 403
            if user.is_admin():
                return f(*args, **kwargs)
            if allow_sysadmin and is_sys_admin_role(user.role):
                return f(*args, **kwargs)
            return jsonify({'error': 'Admin access required'}), 403
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

@tenant_bp.route('/', methods=['GET'])
@tenant_bp.route('', methods=['GET'])  # Support both / and no slash
@jwt_required()
@require_admin(allow_sysadmin=True)
def get_tenants():
    from flask import request, jsonify
    import logging
    trace_logger = logging.getLogger('trace')
    
    """
    Get all tenants (admin only)
    
    Returns a paginated list of all tenants in the system.
    Only accessible by admin users.
    """
    
    # [TRACE] Logging
    trace_logger.info(f"[TRACE] Backend: GET /tenants")
    trace_logger.info(f"[TRACE] Backend: Path: {request.path}")
    trace_logger.info(f"[TRACE] Backend: Full path: {request.full_path}")
    trace_logger.info(f"[TRACE] Backend: Query params: {dict(request.args)}")
    
    try:
        from flask_jwt_extended import get_jwt_identity, get_jwt
        current_user_id = get_jwt_identity()
        claims = get_jwt() or {}
        trace_logger.info(f"[TRACE] Backend: User ID: {current_user_id}")
        trace_logger.info(f"[TRACE] Backend: Role: {claims.get('role')}")
        trace_logger.info(f"[TRACE] Backend: Username: {claims.get('username')}")
    except:
        pass
    
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404

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
        
        # Query tenants with pagination
        tenants_query = Tenant.query.order_by(Tenant.created_at.desc())
        if not user.is_admin():
            tenants_query = tenants_query.filter_by(tenantID=user.tenantID)

        tenants_pagination = tenants_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        tenants = [tenant.to_dict() for tenant in tenants_pagination.items]
        
        import logging
        trace_logger = logging.getLogger('trace')
        trace_logger.info(f"[TRACE] Backend: Returning {len(tenants)} tenants")
        trace_logger.info(f"[TRACE] Backend: Response structure: {{success: True, data: [{len(tenants)} items], pagination: {{...}}}}")
        
        response = jsonify({
            'success': True,
            'data': tenants,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': tenants_pagination.total,
                'pages': tenants_pagination.pages,
                'has_next': tenants_pagination.has_next,
                'has_prev': tenants_pagination.has_prev
            }
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
        
    except Exception as e:
        logger.error(f"Get tenants error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve tenants', 'details': str(e)}), 500

@tenant_bp.route('/', methods=['POST'])
@jwt_required()
@require_admin()
def create_tenant():
    """
    Create a new tenant (admin only)
    
    Creates a new tenant organization in the system.
    Only accessible by admin users.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate tenant data
        tenant_schema = TenantSchema()
        errors = tenant_schema.validate(data)
        if errors:
            return jsonify({'error': 'Invalid tenant data', 'details': errors}), 400
        
        # Sanitize input
        tenant_name = sanitize_input(data['tenantName'])
        
        # Check if tenant name already exists
        existing_tenant = Tenant.find_by_name(tenant_name)
        if existing_tenant:
            return jsonify({'error': 'Tenant with this name already exists'}), 409
        
        # Create tenant
        tenant = Tenant(
            tenantName=tenant_name,
            is_active=data.get('is_active', True)
        )
        
        db.session.add(tenant)
        db.session.commit()
        
        logger.info(f"New tenant created: {tenant.tenantName} by user: {get_jwt_identity()}")
        
        return jsonify({
            'success': True,
            'message': 'Tenant created successfully',
            'data': tenant.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create tenant error: {str(e)}")
        return jsonify({'error': 'Failed to create tenant', 'details': str(e)}), 500

@tenant_bp.route('/<tenant_id>', methods=['GET'])
@jwt_required()
def get_tenant(tenant_id):
    """
    Get specific tenant information
    
    Returns detailed information about a specific tenant.
    Users can only access their own tenant unless they are admin.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find tenant
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # Check access permissions
        if not user.is_admin():
            if not (is_sys_admin_role(user.role) and user.tenantID == tenant_id):
                return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'data': tenant.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Get tenant error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve tenant', 'details': str(e)}), 500

@tenant_bp.route('/<tenant_id>', methods=['PUT'])
@jwt_required()
@require_admin()
def update_tenant(tenant_id):
    """
    Update tenant information (admin only)
    
    Updates the information of a specific tenant.
    Only accessible by admin users.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate update data
        update_schema = TenantUpdateSchema()
        errors = update_schema.validate(data)
        if errors:
            return jsonify({'error': 'Invalid update data', 'details': errors}), 400
        
        # Find tenant
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # Update fields
        if 'tenantName' in data:
            tenant_name = sanitize_input(data['tenantName'])
            
            # Check if new name conflicts with existing tenant
            existing_tenant = Tenant.find_by_name(tenant_name)
            if existing_tenant and existing_tenant.tenantID != tenant_id:
                return jsonify({'error': 'Tenant with this name already exists'}), 409
            
            tenant.tenantName = tenant_name
        
        if 'is_active' in data:
            tenant.is_active = data['is_active']
        
        tenant.updated_at = db.func.now()
        db.session.commit()
        
        logger.info(f"Tenant updated: {tenant.tenantID} by user: {get_jwt_identity()}")
        
        return jsonify({
            'success': True,
            'message': 'Tenant updated successfully',
            'data': tenant.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update tenant error: {str(e)}")
        return jsonify({'error': 'Failed to update tenant', 'details': str(e)}), 500

@tenant_bp.route('/<tenant_id>', methods=['DELETE'])
@jwt_required()
@require_admin()
def delete_tenant(tenant_id):
    """
    Delete tenant (admin only)
    
    Soft deletes a tenant by setting is_active to False.
    Only accessible by admin users.
    """
    try:
        # Find tenant
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # Soft delete (deactivate)
        tenant.is_active = False
        tenant.updated_at = db.func.now()
        
        # Also deactivate all users in this tenant
        for user in tenant.users:
            user.status = 'inactive'
        
        db.session.commit()
        
        logger.info(f"Tenant deactivated: {tenant.tenantID} by user: {get_jwt_identity()}")
        
        return jsonify({
            'success': True,
            'message': 'Tenant deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete tenant error: {str(e)}")
        return jsonify({'error': 'Failed to delete tenant', 'details': str(e)}), 500

@tenant_bp.route('/<tenant_id>/stats', methods=['GET'])
@jwt_required()
def get_tenant_stats(tenant_id):
    """
    Get tenant statistics
    
    Returns statistics about the tenant including user counts,
    department counts, and recent activity.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check access permissions
        if not user.is_admin():
            if not (is_sys_admin_role(user.role) and user.tenantID == tenant_id):
                return jsonify({'error': 'Access denied'}), 403
        
        # Find tenant
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # Get statistics
        stats = {
            'tenant': tenant.to_dict(),
            'users': {
                'total': tenant.users.count(),
                'active': len(tenant.get_active_users()),
                'by_role': {}
            },
            'departments': {
                'total': tenant.departments.count(),
                'active': len(tenant.get_active_departments())
            },
            'schedule_definitions': {
                'total': tenant.schedule_definitions.count(),
                'active': tenant.schedule_definitions.filter_by(is_active=True).count()
            },
            'recent_jobs': len(tenant.get_recent_job_logs(5))
        }
        
        # Count users by role
        for user_obj in tenant.users:
            role = user_obj.role
            if role not in stats['users']['by_role']:
                stats['users']['by_role'][role] = 0
            stats['users']['by_role'][role] += 1
        
        return jsonify({
            'success': True,
            'data': stats
        }), 200
        
    except Exception as e:
        logger.error(f"Get tenant stats error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve tenant statistics', 'details': str(e)}), 500

@tenant_bp.route('/<tenant_id>/users', methods=['GET'])
@jwt_required()
def get_tenant_users(tenant_id):
    """
    Get all users for a specific tenant
    
    Returns a list of all users belonging to the specified tenant.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check access permissions
        if not user.is_admin():
            if not (is_sys_admin_role(user.role) and user.tenantID == tenant_id):
                return jsonify({'error': 'Access denied'}), 403
        
        # Find tenant
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # Get users
        users = [user_obj.to_dict() for user_obj in tenant.users]
        
        return jsonify({
            'success': True,
            'data': users
        }), 200
        
    except Exception as e:
        logger.error(f"Get tenant users error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve tenant users', 'details': str(e)}), 500

# Error handlers
@tenant_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found errors"""
    return jsonify({'error': 'Resource not found'}), 404

@tenant_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden errors"""
    return jsonify({'error': 'Access denied'}), 403







