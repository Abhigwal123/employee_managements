# Schedule Definition Routes
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import ScheduleDefinition, User, Department
try:
    from app.schemas import ScheduleDefinitionSchema, ScheduleDefinitionUpdateSchema, PaginationSchema
    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False
    ScheduleDefinitionSchema = None
    ScheduleDefinitionUpdateSchema = None
    PaginationSchema = None
from app.utils.security import sanitize_input
from app.utils.role_utils import is_client_admin_role, is_schedule_manager_role
from app.utils.tenant_filter import get_tenant_filtered_query
import logging

logger = logging.getLogger(__name__)

schedule_definition_bp = Blueprint('schedule_definitions', __name__)

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

@schedule_definition_bp.route('/', methods=['GET'])
@schedule_definition_bp.route('', methods=['GET'])  # Support both / and no slash
@jwt_required()
def get_schedule_definitions():
    """Get schedule definitions for current tenant (ClientAdmin can access all tenants)"""
    import logging
    trace_logger = logging.getLogger('trace')
    
    # Handle CORS preflight
    # [TRACE] Logging
    trace_logger.info(f"[TRACE] Backend: GET /schedule-definitions")
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
                per_page = int(min(pagination_data.get('per_page', 20), 100))
            else:
                page = int(request.args.get('page', 1) or 1)
                per_page = int(min(int(request.args.get('per_page', 20) or 20), 100))
        except Exception:
            page = 1
            per_page = 20
        
        # Query schedule definitions - ClientAdmin sees all, others see only their tenant
        definitions_query = get_tenant_filtered_query(ScheduleDefinition, user)
        
        # Apply department filter if specified
        department_filter = request.args.get('department_id')
        if department_filter:
            definitions_query = definitions_query.filter_by(departmentID=department_filter)
        
        # Apply active filter if specified
        active_filter = request.args.get('active')
        if active_filter is not None:
            is_active = active_filter.lower() == 'true'
            definitions_query = definitions_query.filter_by(is_active=is_active)
        
        definitions_pagination = definitions_query.order_by(ScheduleDefinition.created_at.desc()).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Sync Google Sheets metadata for each schedule definition before returning
        # This ensures the frontend always gets the latest data from Google Sheets
        definitions_with_sync = []
        for defn in definitions_pagination.items:
            try:
                # Sync metadata from Google Sheets (non-blocking, graceful fallback)
                from flask import current_app
                from app.services.google_sheets_sync_service import GoogleSheetsSyncService
                
                creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
                sync_service = GoogleSheetsSyncService(creds_path)
                
                # Sync metadata (fetches from Google Sheets and updates DB)
                sync_result = sync_service.sync_schedule_definition_metadata(defn, creds_path)
                
                if sync_result.get('success'):
                    logger.info(f"[Google Sheets Sync] Synced metadata for {defn.scheduleName}: {sync_result.get('row_count', 0)} rows")
                elif sync_result.get('skipped'):
                    # Gracefully skip if sheets not available - continue with DB data
                    logger.debug(f"[Google Sheets Sync] Skipped sync for {defn.scheduleName}: {sync_result.get('error', 'Unknown')}")
                else:
                    # Log error but continue - don't fail the request
                    logger.warning(f"[Google Sheets Sync Error] Sync failed for {defn.scheduleName}: {sync_result.get('error', 'Unknown')}")
            except Exception as sync_err:
                # Log error but continue - ensure API always returns data
                logger.warning(f"[Google Sheets Sync Error] Error syncing {defn.scheduleName}: {str(sync_err)}")
            
            # Convert to dict (after sync, so metadata is up to date)
            definitions_with_sync.append(defn.to_dict())
        
        definitions = definitions_with_sync

        # Auto-sync: If no schedule definitions found and this is the first page, trigger sync
        if len(definitions) == 0 and page == 1 and definitions_pagination.total == 0:
            logger.info("[AUTO-SYNC] No schedule definitions found, checking if schedule data needs syncing...")
            try:
                from app.utils.auto_sync import sync_all_active_schedules_if_empty
                sync_result = sync_all_active_schedules_if_empty(tenant_id=user.tenantID)
                if sync_result:
                    logger.info(f"[AUTO-SYNC] Schedule sync result: {sync_result.get('success')}")
            except Exception as sync_err:
                logger.warning(f"[AUTO-SYNC] Error during auto-sync: {str(sync_err)}")

        import logging
        trace_logger = logging.getLogger('trace')
        trace_logger.info(f"[TRACE] Backend: Returning {len(definitions)} schedule definitions")
        trace_logger.info(f"[TRACE] Backend: Response structure: {{page: {page}, per_page: {per_page}, total: {definitions_pagination.total}, items: [{len(definitions)} items]}}")

        # Return normalized structure
        response = jsonify({
            'page': page,
            'per_page': per_page,
            'total': definitions_pagination.total,
            'items': definitions
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
        
    except Exception as e:
        logger.error(f"Get schedule definitions error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        response = jsonify({'error': 'Failed to retrieve schedule definitions', 'details': str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

@schedule_definition_bp.route('/', methods=['POST'])
@jwt_required()
@require_admin_or_scheduler()
def create_schedule_definition():
    """Create a new schedule definition"""
    try:
        current_user = get_current_user()
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate schedule definition data
        definition_schema = ScheduleDefinitionSchema()
        errors = definition_schema.validate(data)
        if errors:
            return jsonify({'error': 'Invalid schedule definition data', 'details': errors}), 400
        
        # Sanitize input
        schedule_name = sanitize_input(data['scheduleName'])
        
        # Check if schedule name already exists in tenant
        existing_defn = ScheduleDefinition.find_by_name(current_user.tenantID, schedule_name)
        if existing_defn:
            return jsonify({'error': 'Schedule definition with this name already exists'}), 409
        
        # Verify department belongs to tenant
        department = Department.query.get(data['departmentID'])
        if not department or department.tenantID != current_user.tenantID:
            return jsonify({'error': 'Invalid department'}), 400
        
        # Create schedule definition
        definition = ScheduleDefinition(
            tenantID=current_user.tenantID,
            departmentID=data['departmentID'],
            scheduleName=schedule_name,
            paramsSheetURL=data['paramsSheetURL'],
            prefsSheetURL=data['prefsSheetURL'],
            resultsSheetURL=data['resultsSheetURL'],
            schedulingAPI=data['schedulingAPI'],
            remarks=data.get('remarks'),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(definition)
        db.session.commit()
        
        logger.info(f"New schedule definition created: {definition.scheduleName} by user: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Schedule definition created successfully',
            'data': definition.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create schedule definition error: {str(e)}")
        return jsonify({'error': 'Failed to create schedule definition', 'details': str(e)}), 500

@schedule_definition_bp.route('/<definition_id>', methods=['GET'])
@jwt_required()
def get_schedule_definition(definition_id):
    """Get specific schedule definition information"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find schedule definition
        definition = ScheduleDefinition.query.get(definition_id)
        if not definition:
            return jsonify({'error': 'Schedule definition not found'}), 404
        
        # Check tenant access
        if user.tenantID != definition.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'data': definition.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Get schedule definition error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve schedule definition', 'details': str(e)}), 500

@schedule_definition_bp.route('/<definition_id>', methods=['PUT'])
@jwt_required()
@require_admin_or_scheduler()
def update_schedule_definition(definition_id):
    """Update schedule definition information"""
    try:
        current_user = get_current_user()
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate update data
        update_schema = ScheduleDefinitionUpdateSchema()
        errors = update_schema.validate(data)
        if errors:
            return jsonify({'error': 'Invalid update data', 'details': errors}), 400
        
        # Find schedule definition
        definition = ScheduleDefinition.query.get(definition_id)
        if not definition:
            return jsonify({'error': 'Schedule definition not found'}), 404
        
        # Check tenant access
        if current_user.tenantID != definition.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update fields
        if 'scheduleName' in data:
            schedule_name = sanitize_input(data['scheduleName'])
            
            # Check if new name conflicts
            existing_defn = ScheduleDefinition.find_by_name(current_user.tenantID, schedule_name)
            if existing_defn and existing_defn.scheduleDefID != definition_id:
                return jsonify({'error': 'Schedule definition with this name already exists'}), 409
            
            definition.scheduleName = schedule_name
        
        if 'departmentID' in data:
            # Verify department belongs to tenant
            department = Department.query.get(data['departmentID'])
            if not department or department.tenantID != current_user.tenantID:
                return jsonify({'error': 'Invalid department'}), 400
            definition.departmentID = data['departmentID']
        
        if 'paramsSheetURL' in data:
            definition.paramsSheetURL = data['paramsSheetURL']
        
        if 'prefsSheetURL' in data:
            definition.prefsSheetURL = data['prefsSheetURL']
        
        # Track URL changes to trigger auto-regeneration
        url_changed = False
        if 'resultsSheetURL' in data:
            old_url = definition.resultsSheetURL
            definition.resultsSheetURL = data['resultsSheetURL']
            if old_url != data['resultsSheetURL']:
                url_changed = True
                logger.info(f"[SCHEDULE] ResultsSheetURL changed for schedule: {definition.scheduleName}")
                logger.info(f"[SCHEDULE] Old URL: {old_url}")
                logger.info(f"[SCHEDULE] New URL: {data['resultsSheetURL']}")
        
        if 'schedulingAPI' in data:
            definition.schedulingAPI = data['schedulingAPI']
        
        if 'remarks' in data:
            definition.remarks = data['remarks']
        
        if 'is_active' in data:
            definition.is_active = data['is_active']
        
        definition.updated_at = db.func.now()
        db.session.commit()
        
        logger.info(f"Schedule definition updated: {definition.scheduleName} by user: {current_user.username}")
        
        # Trigger auto-regeneration if URL changed
        if url_changed:
            try:
                from app.services.auto_regeneration_service import AutoRegenerationService
                from flask import current_app
                
                creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
                auto_regen_service = AutoRegenerationService(credentials_path=creds_path)
                
                # Trigger regeneration in background (non-blocking)
                import threading
                def regenerate_in_background():
                    try:
                        result = auto_regen_service.validate_and_regenerate(definition.scheduleDefID)
                        if result.get('regenerated'):
                            logger.info(f"[SCHEDULE] Auto-regeneration triggered after URL change for schedule: {definition.scheduleName}")
                        else:
                            logger.info(f"[SCHEDULE] Auto-regeneration not needed: {result.get('reason', 'unknown')}")
                    except Exception as e:
                        logger.error(f"[SCHEDULE] Error during auto-regeneration after URL change: {e}")
                
                # Start background thread
                thread = threading.Thread(target=regenerate_in_background)
                thread.daemon = True
                thread.start()
                logger.info(f"[SCHEDULE] Started background auto-regeneration thread for schedule: {definition.scheduleName}")
            except Exception as e:
                logger.warning(f"[SCHEDULE] Failed to trigger auto-regeneration after URL change: {e}")
                # Don't fail the update request if regeneration fails
        
        return jsonify({
            'success': True,
            'message': 'Schedule definition updated successfully',
            'data': definition.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update schedule definition error: {str(e)}")
        return jsonify({'error': 'Failed to update schedule definition', 'details': str(e)}), 500

@schedule_definition_bp.route('/<definition_id>', methods=['DELETE'])
@jwt_required()
@require_admin_or_scheduler()
def delete_schedule_definition(definition_id):
    """Delete schedule definition (soft delete)"""
    try:
        current_user = get_current_user()
        
        # Find schedule definition
        definition = ScheduleDefinition.query.get(definition_id)
        if not definition:
            return jsonify({'error': 'Schedule definition not found'}), 404
        
        # Check tenant access
        if current_user.tenantID != definition.tenantID:
            return jsonify({'error': 'Access denied'}), 403
        
        # Soft delete (deactivate)
        definition.is_active = False
        definition.updated_at = db.func.now()
        db.session.commit()
        
        logger.info(f"Schedule definition deactivated: {definition.scheduleName} by user: {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Schedule definition deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete schedule definition error: {str(e)}")
        return jsonify({'error': 'Failed to delete schedule definition', 'details': str(e)}), 500







