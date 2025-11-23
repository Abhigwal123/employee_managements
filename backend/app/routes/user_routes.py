# User Routes
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import User, Tenant, EmployeeMapping, SchedulePermission
from ..utils.auth import role_required
from ..utils.role_utils import EMPLOYEE_ROLE, normalize_role
try:
    from ..schemas import UserSchema, UserUpdateSchema, PaginationSchema
    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False
    UserSchema = None
    UserUpdateSchema = None
    PaginationSchema = None
from ..utils.security import sanitize_input
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

user_bp = Blueprint('users', __name__)


def get_current_user():
    """Get current authenticated user"""
    current_user_id = get_jwt_identity()
    return User.query.get(current_user_id)

def require_admin_or_self():
    """Decorator to require admin role or self access"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            current_user = get_current_user()
            if not current_user:
                return jsonify({'error': 'User not found'}), 404
            
            # ClientAdmin can access any user, others can only access themselves
            is_admin = current_user.is_admin()
            
            # Extract user_id from kwargs (route parameter)
            user_id = kwargs.get('user_id')
            
            if not is_admin and (not user_id or current_user.userID != user_id):
                return jsonify({'error': 'Access denied'}), 403
            
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

@user_bp.route('/', methods=['GET'])
@user_bp.route('', methods=['GET'])  # Support both / and no slash
@jwt_required()
@role_required("ClientAdmin")
def get_users():
    """Get users for current tenant"""
    import logging
    trace_logger = logging.getLogger('trace')
    
    trace_logger.info("[TRACE] Backend: GET /users")
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
        
        # Query users for current tenant
        users_query = User.query.filter_by(tenantID=user.tenantID)
        
        # Apply role filter if specified
        role_filter = request.args.get('role')
        if role_filter:
            users_query = users_query.filter_by(role=role_filter)
        
        # Apply status filter if specified
        status_filter = request.args.get('status')
        if status_filter:
            users_query = users_query.filter_by(status=status_filter)
        
        users_pagination = users_query.order_by(User.created_at.desc()).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        users = [user_obj.to_dict() for user_obj in users_pagination.items]
        
        # Auto-sync: If no users found and this is the first page, trigger sync for schedule data
        # Note: Users are typically created manually, but we can sync schedule data if cache is empty
        if len(users) == 0 and page == 1 and users_pagination.total == 0:
            logger.info("[AUTO-SYNC] No users found in database, checking if schedule data needs syncing...")
            try:
                from app.utils.auto_sync import sync_all_active_schedules_if_empty
                sync_result = sync_all_active_schedules_if_empty(tenant_id=user.tenantID)
                if sync_result:
                    logger.info(f"[AUTO-SYNC] Schedule sync result: {sync_result.get('success')}")
            except Exception as sync_err:
                logger.warning(f"[AUTO-SYNC] Error during auto-sync: {str(sync_err)}")
        
        trace_logger.info(f"[TRACE] Backend: Returning {len(users)} users")
        trace_logger.info(f"[TRACE] Backend: Response structure: {{success: True, data: [{len(users)} items], pagination: {{...}}}}")
        
        response = jsonify({
            'success': True,
            'data': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': users_pagination.total,
                'pages': users_pagination.pages,
                'has_next': users_pagination.has_next,
                'has_prev': users_pagination.has_prev
            }
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
        
    except Exception as e:
        logger.error(f"Get users error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve users', 'details': str(e)}), 500

@user_bp.route('/', methods=['POST'])
@jwt_required()
@role_required("ClientAdmin")
def create_user():
    """Create a new user (admin only)"""
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is ClientAdmin
        is_admin = current_user.is_admin()
        
        if not is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate user data (inject tenantID so schema passes when frontend omits it)
        user_schema = UserSchema()
        schema_payload = dict(data)
        schema_payload.setdefault('tenantID', current_user.tenantID)
        errors = user_schema.validate(schema_payload)
        if errors:
            return jsonify({'error': 'Invalid user data', 'details': errors}), 400
        
        # Normalize role representations
        requested_role = data.get('role', 'Department_Employee')
        normalized_role = normalize_role(requested_role)
        
        # Sanitize username input
        username = sanitize_input(data['username'])
        if not username:
            return jsonify({'error': 'Username cannot be empty'}), 400
        
        # For employee-level roles, username must match the employee identifier
        employee_id = data.get('employee_id')
        if normalized_role == EMPLOYEE_ROLE:
            identifier = employee_id or username
            identifier = identifier.strip().upper() if isinstance(identifier, str) else None
            if not identifier:
                return jsonify({'error': 'Employee ID is required for employee accounts'}), 400
            employee_id = identifier
            username = identifier  # enforce username == employee identifier
        elif isinstance(employee_id, str):
            employee_id = employee_id.strip().upper()
        
        # Check if username already exists (case-insensitive)
        existing_user = User.find_by_username(username)
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 409
        
        # Ensure employee_id uniqueness when provided
        if employee_id:
            existing_employee = User.find_by_employee_id(employee_id)
            if existing_employee:
                return jsonify({'error': 'Employee ID already linked to another account'}), 409
        
        # Create user
        # Handle status field - convert is_active boolean to status string if needed
        status = data.get('status', 'active')
        if 'is_active' in data and 'status' not in data:
            status = 'active' if data['is_active'] else 'inactive'
        
        user = User(
            tenantID=current_user.tenantID,
            username=username,
            password=data['password'],
            role=requested_role,
            status=status,
            email=data.get('email'),
            full_name=data.get('full_name'),
            employee_id=employee_id
        )
        
        db.session.add(user)
        db.session.flush()  # Flush to get userID
        
        # 🔗 Auto-link EmployeeMapping for employee role (same logic as registration)
        if normalized_role == EMPLOYEE_ROLE and employee_id:
            if not EmployeeMapping:
                logger.warning("[WARN][ADMIN_CREATE] EmployeeMapping model unavailable; skipping auto-link.")
            else:
                normalized_identifier = employee_id.upper()
                
                # Attempt to find matching EmployeeMapping
                employee_mapping = EmployeeMapping.find_by_sheets_identifier(normalized_identifier)
                
                if employee_mapping:
                    # Safety check: ensure mapping is not already linked to another user
                    if employee_mapping.userID and employee_mapping.userID != user.userID:
                        existing_user = User.query.get(employee_mapping.userID)
                        logger.warning(f"[WARN][ADMIN_CREATE] EmployeeMapping for '{normalized_identifier}' already linked to user '{existing_user.username if existing_user else employee_mapping.userID}'")
                    else:
                        # Link the found mapping
                        logger.info(f"[TRACE][ADMIN_CREATE] Employee auto-linked: {normalized_identifier} -> userID {user.userID}")
                        employee_mapping.userID = user.userID
                        employee_mapping.tenantID = current_user.tenantID  # Ensure tenant matches
                        employee_mapping.is_active = True
                        employee_mapping.updated_at = datetime.utcnow()
                        
                        # Also link any other EmployeeMapping records with the same sheets_identifier and tenant
                        other_mappings = EmployeeMapping.query.filter(
                            EmployeeMapping.sheets_identifier == normalized_identifier,
                            EmployeeMapping.tenantID == current_user.tenantID,
                            EmployeeMapping.userID.is_(None),
                            EmployeeMapping.is_active == True
                        ).all()
                        
                        for other_mapping in other_mappings:
                            if other_mapping.mappingID != employee_mapping.mappingID:
                                other_mapping.userID = user.userID
                                other_mapping.updated_at = datetime.utcnow()
                                logger.info(f"[TRACE][ADMIN_CREATE] Linked additional EmployeeMapping {other_mapping.mappingID} to user {user.userID}")
                        
                        # Ensure user.employee_id is set
                        if not user.employee_id or user.employee_id.upper() != normalized_identifier:
                            user.employee_id = normalized_identifier
                            logger.info(f"[TRACE][ADMIN_CREATE] Set user.employee_id to '{normalized_identifier}'")
                else:
                    logger.warning(f"[WARN][ADMIN_CREATE] No EmployeeMapping found for '{normalized_identifier}'. User created but not linked to employee mapping.")
        
        db.session.commit()
        
        logger.info(f"[TRACE][ADMIN_CREATE] New user created: {user.username} (employee_id: {user.employee_id or 'None'}) by admin: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'data': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create user error: {str(e)}")
        return jsonify({'error': 'Failed to create user', 'details': str(e)}), 500

@user_bp.route('/<user_id>', methods=['GET'])
@jwt_required()
@role_required("ClientAdmin")
@require_admin_or_self()
def get_user(user_id):
    """Get specific user information"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        current_user = get_current_user()
        
        # Check access permissions - allow ClientAdmin
        is_admin = current_user.is_admin()
        
        if not is_admin and current_user.tenantID != user.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'data': user.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve user', 'details': str(e)}), 500

@user_bp.route('/<user_id>', methods=['PUT'])
@jwt_required()
@role_required("ClientAdmin")
@require_admin_or_self()
def update_user(user_id):
    """Update user information"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate update data
        update_schema = UserUpdateSchema()
        errors = update_schema.validate(data)
        if errors:
            return jsonify({'error': 'Invalid update data', 'details': errors}), 400
        
        # Find user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        current_user = get_current_user()
        
        # Check access permissions - allow ClientAdmin
        is_admin = current_user.is_admin()
        
        if not is_admin and current_user.tenantID != user.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        # Determine current and target roles for employee-specific handling
        current_normalized_role = normalize_role(user.role)
        requested_role_raw = data.get('role')
        requested_role = requested_role_raw if (is_admin and requested_role_raw) else user.role
        target_normalized_role = normalize_role(requested_role)
        will_be_employee = target_normalized_role == EMPLOYEE_ROLE
        was_employee = current_normalized_role == EMPLOYEE_ROLE
        
        # Handle username updates
        new_username = user.username
        if 'username' in data and data['username'] is not None:
            candidate_username = sanitize_input(data['username'])
            if not candidate_username:
                return jsonify({'error': 'Username cannot be empty'}), 400
            
            existing_user = User.find_by_username(candidate_username)
            if existing_user and existing_user.userID != user_id:
                return jsonify({'error': 'Username already exists'}), 409
            
            new_username = candidate_username
        
        # Handle employee_id updates (may be required for employee roles)
        new_employee_id = user.employee_id
        employee_id_provided = 'employee_id' in data
        if employee_id_provided:
            candidate_employee_id = data.get('employee_id')
            candidate_employee_id = candidate_employee_id.strip().upper() if isinstance(candidate_employee_id, str) else None
            if candidate_employee_id:
                existing_employee = User.find_by_employee_id(candidate_employee_id)
                if existing_employee and existing_employee.userID != user_id:
                    return jsonify({'error': 'Employee ID already linked to another account'}), 409
            new_employee_id = candidate_employee_id
        
        # Employee accounts must use the employee identifier for both username and employee_id
        if will_be_employee:
            identifier_source = new_employee_id or new_username or user.employee_id
            identifier_source = identifier_source.strip().upper() if isinstance(identifier_source, str) else None
            if not identifier_source:
                return jsonify({'error': 'Employee ID is required for employee accounts'}), 400
            
            existing_employee = User.find_by_employee_id(identifier_source)
            if existing_employee and existing_employee.userID != user_id:
                return jsonify({'error': 'Employee ID already linked to another account'}), 409
            
            new_employee_id = identifier_source
            new_username = identifier_source
        elif was_employee and not will_be_employee and not employee_id_provided:
            # When converting from employee to another role, clear employee_id unless explicitly provided
            new_employee_id = None
        
        if new_username != user.username:
            user.username = new_username
        
        if new_employee_id != user.employee_id:
            user.employee_id = new_employee_id
        
        # Password update - only for ClientAdmin, hash the password
        if 'password' in data and data['password'] and is_admin:
            user.set_password(data['password'])
            logger.info(f"Password updated for user: {user.username} by admin: {current_user.username}")
        
        # Role update - only for ClientAdmin
        if is_admin:
            user.role = requested_role
        
        # Status update - only for ClientAdmin
        if 'status' in data and data['status'] and is_admin:
            user.status = data['status']
        elif 'is_active' in data and is_admin:
            # Handle frontend sending is_active boolean
            user.status = 'active' if data['is_active'] else 'inactive'
        
        if 'email' in data:
            user.email = data['email']
        
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        # Synchronize employee mappings if necessary
        if EmployeeMapping:
            if will_be_employee and new_employee_id:
                normalized_identifier = new_employee_id.upper()
                mappings = EmployeeMapping.query.filter_by(userID=user.userID).all()
                if mappings:
                    for mapping in mappings:
                        mapping.sheets_identifier = normalized_identifier
                        mapping.is_active = True
                        mapping.updated_at = datetime.utcnow()
                else:
                    mapping = EmployeeMapping.find_by_sheets_identifier(normalized_identifier)
                    if mapping and mapping.userID and mapping.userID != user.userID:
                        logger.warning(f"[WARN][ADMIN_UPDATE] EmployeeMapping for '{normalized_identifier}' already linked to user '{mapping.userID}'")
                    elif mapping:
                        mapping.userID = user.userID
                        mapping.tenantID = user.tenantID
                        mapping.is_active = True
                        mapping.updated_at = datetime.utcnow()
                    else:
                        logger.warning(f"[WARN][ADMIN_UPDATE] No EmployeeMapping found for '{normalized_identifier}'.")
            elif was_employee and not will_be_employee:
                mappings = EmployeeMapping.query.filter_by(userID=user.userID).all()
                for mapping in mappings:
                    mapping.userID = None
                    mapping.updated_at = datetime.utcnow()
        
        # Note: departmentID is not stored on User model today. Placeholder retained for future use.
        if 'departmentID' in data:
            pass
        
        user.updated_at = db.func.now()
        db.session.commit()
        
        logger.info(f"User updated: {user.username} by user: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully',
            'data': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update user error: {str(e)}")
        return jsonify({'error': 'Failed to update user', 'details': str(e)}), 500

@user_bp.route('/<user_id>', methods=['DELETE'])
@jwt_required()
@role_required("ClientAdmin")
def delete_user(user_id):
    """Delete user (admin only)"""
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is ClientAdmin
        is_admin = current_user.is_admin()
        
        if not is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Find user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check tenant access
        if current_user.tenantID != user.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        # Soft delete (deactivate)
        user.status = 'inactive'
        user.updated_at = db.func.now()
        db.session.commit()
        
        logger.info(f"User deactivated: {user.username} by admin: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'User deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete user error: {str(e)}")
        return jsonify({'error': 'Failed to delete user', 'details': str(e)}), 500


@user_bp.route('/<user_id>/role', methods=['PUT'])
@jwt_required()
@role_required("ClientAdmin")
def update_user_role(user_id):
    """
    PUT /api/v1/users/<user_id>/role
    curl -X PUT /api/v1/users/USER123/role -H "Authorization: Bearer <token>" -d '{"role":"ClientAdmin"}'
    """
    data = request.get_json() or {}
    new_role = data.get('role')
    if not new_role:
        return jsonify({'error': 'role is required'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.role = normalize_role(new_role)
    user.updated_at = db.func.now()
    db.session.commit()
    
    return jsonify({'success': True, 'data': user.to_dict()}), 200


@user_bp.route('/<user_id>/permissions', methods=['GET'])
@jwt_required()
@role_required("ClientAdmin")
def get_user_permissions(user_id):
    """
    GET /api/v1/users/<user_id>/permissions
    curl /api/v1/users/USER123/permissions -H "Authorization: Bearer <token>"
    """
    permissions = SchedulePermission.query.filter_by(userID=user_id).all()
    return jsonify({
        'success': True,
        'data': [perm.to_dict() for perm in permissions]
    }), 200


@user_bp.route('/<user_id>/permissions', methods=['PUT'])
@jwt_required()
@role_required("ClientAdmin")
def update_user_permissions(user_id):
    """
    PUT /api/v1/users/<user_id>/permissions
    curl -X PUT /api/v1/users/USER123/permissions -H "Authorization: Bearer <token>" -d '{"permissions":[...]}'
    """
    payload = request.get_json() or {}
    entries = payload.get('permissions', [])
    
    try:
        result = SchedulePermission.sync_for_user(user_id=user_id, entries=entries)
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    
    db.session.commit()
    return jsonify({'success': True, 'summary': result}), 200

