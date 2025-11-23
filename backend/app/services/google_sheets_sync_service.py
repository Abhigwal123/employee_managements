"""
Google Sheets Sync Service
Syncs data from Google Sheets to local database cache
Implements exponential backoff for rate limit errors
"""
import logging
import re
import traceback
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import time

from .. import db

# Import models with error handling
try:
    from ..models import ScheduleDefinition, User, EmployeeMapping, CachedSchedule, SyncLog
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"[ERROR][SYNC] Missing model import: {e}")
    raise ImportError(f"[ERROR][SYNC] Failed to import required models. Please ensure all models are available: {e}")

from .dashboard_data_service import DashboardDataService
# CRITICAL: Import the module instead of the function directly to get the wrapped version
from . import google_sheets_import as sheets_import_module
# Get fetch_schedule_data from module to ensure we use the wrapped version
fetch_schedule_data = None  # Will be set after import

logger = logging.getLogger(__name__)

# Validate critical imports
if not ScheduleDefinition:
    logger.error("[ERROR][SYNC] ScheduleDefinition model not available")
if not User:
    logger.error("[ERROR][SYNC] User model not available")
if not EmployeeMapping:
    logger.error("[ERROR][SYNC] EmployeeMapping model not available")

class GoogleSheetsSyncService:
    """Service to sync Google Sheets data to database cache"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path
    
    def sync_schedule_data(self, schedule_def_id: str, sync_type: str = 'auto', 
                          triggered_by: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        Sync schedule data from Google Sheets to database
        
        Args:
            schedule_def_id: Schedule definition ID
            sync_type: Type of sync ('auto', 'manual', 'scheduled')
            triggered_by: User ID who triggered sync (for manual syncs)
            force: Force sync even if recent sync exists
            
        Returns:
            Dictionary with sync results
        """
        schedule_def = ScheduleDefinition.query.get(schedule_def_id)
        if not schedule_def:
            return {
                'success': False,
                'error': f'Schedule definition not found: {schedule_def_id}'
            }
        
        # CRITICAL: Always fetch from Google Sheets when force=True or sync_type='on_demand'
        # This ensures we fetch fresh data from Google Sheets, not just check DB
        if not force and sync_type != 'on_demand':
            # Use shorter threshold for auto requests (5 minutes)
            min_threshold = 5 if sync_type == 'auto' else 10
            if not SyncLog.should_sync(schedule_def_id=schedule_def_id, min_minutes=min_threshold):
                last_sync = SyncLog.get_last_sync(schedule_def_id=schedule_def_id)
                logger.info(f"[SYNC] Data is fresh, skipping sync. Last synced: {last_sync.completed_at.isoformat() if last_sync and last_sync.completed_at else 'Never'}")
                return {
                    'success': True,
                    'skipped': True,
                    'message': f'Data is fresh. Last synced: {last_sync.completed_at.isoformat() if last_sync and last_sync.completed_at else "Never"}',
                    'last_synced_at': last_sync.completed_at.isoformat() if last_sync and last_sync.completed_at else None
                }
        
        # For 'on_demand' or 'force=True' syncs, ALWAYS fetch from Google Sheets
        if sync_type == 'on_demand' or force:
            logger.info(f"[SYNC] 🔄 FORCING sync from Google Sheets (type: {sync_type}, force: {force}) - will fetch fresh data")
            logger.info(f"[SYNC] This will fetch ALL data from Google Sheets, not just check database")
        
        # Create sync log
        sync_log = SyncLog.create_sync_log(
            schedule_def_id=schedule_def_id,
            tenant_id=schedule_def.tenantID,
            sync_type=sync_type,
            triggered_by=triggered_by
        )
        
        try:
            logger.info(f"[SYNC] Starting sync for schedule {schedule_def_id} (type: {sync_type})")
            
            # Fetch data from Google Sheets with retry logic
            sheets_data = self._fetch_with_retry(schedule_def_id)
            
            if not sheets_data.get('success'):
                error_msg = sheets_data.get('error', 'Unknown error')
                sync_log.mark_completed(rows_synced=0, users_synced=0, error_message=error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Sync EmployeeMapping records from employee sheet (before storing schedule data)
            logger.info(f"[TRACE][SYNC] Starting EmployeeMapping sync for schedule {schedule_def_id}")
            employee_mappings_synced = self._sync_employee_mappings(schedule_def_id, sheets_data)
            logger.info(f"[TRACE][SYNC] Synced {employee_mappings_synced} EmployeeMapping records from employee sheet")
            
            # Link users to EmployeeMappings after sync (auto-create missing users)
            logger.info(f"[TRACE][SYNC] Linking users to EmployeeMappings (auto-create enabled)...")
            users_linked = self._link_users_to_employee_mappings(schedule_def_id, auto_create_users=True)
            logger.info(f"[TRACE][SYNC] Linked/created {users_linked} users for EmployeeMappings")
            
            # Parse and store schedule data
            logger.info(f"[TRACE][SYNC] Starting schedule data storage for schedule {schedule_def_id}")
            rows_synced, users_synced = self._store_schedule_data(schedule_def_id, sheets_data)
            
            # Mark sync as completed
            sync_log.mark_completed(rows_synced=rows_synced, users_synced=users_synced)
            
            # Final commit to ensure all changes are saved
            db.session.commit()
            
            logger.info(f"[TRACE][SYNC] ✅ Google Sheets -> Database sync complete: {rows_synced} rows, {users_synced} users")
            logger.info(f"[SYNC] Google Sheets -> Database success: {rows_synced} rows, {users_synced} users")
            
            # Log summary
            logger.info(f"[TRACE][SYNC] ========== COMPLETE SYNC SUMMARY ==========")
            logger.info(f"[TRACE][SYNC] EmployeeMappings synced: {employee_mappings_synced}")
            logger.info(f"[TRACE][SYNC] Schedule entries stored: {rows_synced}")
            logger.info(f"[TRACE][SYNC] Users with schedules: {users_synced}")
            logger.info(f"[TRACE][SYNC] ===========================================")
            
            return {
                'success': True,
                'rows_synced': rows_synced,
                'users_synced': users_synced,
                'last_synced_at': sync_log.completed_at.isoformat() if sync_log.completed_at else None,
                'sync_log_id': sync_log.id
            }
            
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            logger.error(f"[SYNC] Sync failed: {error_msg}")
            logger.error(f"[SYNC] Error traceback: {error_trace}")
            
            # CRITICAL: If it's UnboundLocalError for os, provide more context
            if 'UnboundLocalError' in error_msg and 'os' in error_msg:
                logger.error(f"[SYNC] ⚠️ UnboundLocalError for 'os' detected in sync")
                logger.error(f"[SYNC] ⚠️ This suggests fetch_schedule_data wrapper isn't working correctly")
                logger.error(f"[SYNC] ⚠️ Check if sheets_import_module.fetch_schedule_data is the wrapped version")
                # Try to reload the module and retry once
                try:
                    logger.info(f"[SYNC] Attempting to reload google_sheets_import module and retry...")
                    import importlib
                    importlib.reload(sheets_import_module)
                    # Try to get the wrapped version again
                    retry_fetch = sheets_import_module.fetch_schedule_data
                    if retry_fetch:
                        logger.info(f"[SYNC] Retrying with reloaded fetch_schedule_data...")
                        # Don't retry here - just log that we tried
                        # The actual retry should happen at a higher level
                except Exception as reload_error:
                    logger.error(f"[SYNC] Failed to reload module: {reload_error}")
            
            sync_log.mark_completed(rows_synced=0, users_synced=0, error_message=error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'error_type': type(e).__name__,
                'is_unbound_local_os': 'UnboundLocalError' in error_msg and 'os' in error_msg
            }
    
    def _fetch_with_retry(self, schedule_def_id: str, max_retries: int = 3, 
                          initial_delay: float = 2.0) -> Dict[str, Any]:
        """
        Fetch schedule data with exponential backoff retry
        
        Args:
            schedule_def_id: Schedule definition ID
            max_retries: Maximum retry attempts
            initial_delay: Initial delay in seconds
            
        Returns:
            Dictionary with fetched data
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"[SYNC] 🔄 Fetching from Google Sheets API (attempt {attempt + 1}/{max_retries})")
                logger.info(f"[SYNC] This will fetch ALL schedule data from Google Sheets Final Output sheet")
                
                # CRITICAL: Get fetch_schedule_data from module to ensure we use the wrapped version
                current_fetch = sheets_import_module.fetch_schedule_data
                if current_fetch is None:
                    logger.error("[SYNC] fetch_schedule_data is None - Google Sheets service not loaded")
                    # Try to force reload
                    from app.services.google_sheets_import import _try_import_google_sheets
                    success, path = _try_import_google_sheets(force_retry=True)
                    if not success:
                        return {
                            'success': False,
                            'error': 'Google Sheets service not available. Please check logs.'
                        }
                    # Re-import module after reload
                    import importlib
                    importlib.reload(sheets_import_module)
                    current_fetch = sheets_import_module.fetch_schedule_data
                    if current_fetch is None:
                        return {
                            'success': False,
                            'error': 'Failed to load Google Sheets service after retry'
                        }
                
                # CRITICAL: user_role=None to fetch ALL data, not filtered
                try:
                    sheets_data = current_fetch(
                        schedule_def_id,
                        self.credentials_path,
                        user_role=None  # Fetch all data, not filtered by role
                    )
                except Exception as fetch_err:
                    logger.error(f"[SYNC] Exception calling fetch_schedule_data: {fetch_err}")
                    import traceback
                    logger.error(f"[SYNC] Traceback:\n{traceback.format_exc()}")
                    raise
                logger.info(f"[SYNC] ✅ Google Sheets API response received: success={sheets_data.get('success', False)}")
                if sheets_data.get('success'):
                    logger.info(f"[SYNC] 📊 Fetched data structure: {list(sheets_data.get('sheets', {}).keys())}")
                
                if sheets_data.get('success'):
                    return sheets_data
                
                # Check if it's a rate limit error
                error = sheets_data.get('error', '')
                if '429' in str(error) or 'quota' in str(error).lower() or 'rate limit' in str(error).lower():
                    if attempt < max_retries - 1:
                        delay = initial_delay * (2 ** attempt)
                        logger.warning(f"[SYNC] Rate limit error (429), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"[SYNC] Rate limit error after {max_retries} retries")
                        return sheets_data
                
                # For other errors, return immediately
                return sheets_data
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1 and ('429' in error_msg or 'quota' in error_msg.lower()):
                    delay = initial_delay * (2 ** attempt)
                    logger.warning(f"[SYNC] Error: {error_msg}, retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"[SYNC] Fetch failed: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg
                    }
        
        return {
            'success': False,
            'error': 'Failed to fetch after retries'
        }
    
    def _sync_employee_mappings(self, schedule_def_id: str, sheets_data: Dict[str, Any]) -> int:
        """
        Sync EmployeeMapping records from Google Sheets employee sheet
        Handles new employees, removed employees (marked inactive), and name updates.
        
        Args:
            schedule_def_id: Schedule definition ID
            sheets_data: Data from Google Sheets
            
        Returns:
            Number of EmployeeMapping records synced/updated
        """
        mappings_synced = 0
        employees_in_sheet = set()  # Track all employee IDs found in sheet
        employees_added = []  # Track new employees added
        employees_updated = []  # Track employees with name updates
        employees_removed = []  # Track employees marked inactive
        
        try:
            sheets = sheets_data.get('sheets', {})
            
            # PRIORITY 1: Find sheet containing "員工(姓名/ID)" column
            # Target "人員資料庫" sheet or any sheet with the required column
            employee_sheet = None
            target_sheet_name = None
            
            # First, try to find "人員資料庫" sheet specifically
            for sheet_key in ['employee', '人員資料庫']:
                if sheet_key in sheets:
                    sheet_data = sheets[sheet_key]
                    if isinstance(sheet_data, dict) and sheet_data.get('success') and sheet_data.get('data'):
                        columns = sheet_data.get('columns', [])
                        # Check if this sheet has the "員工(姓名/ID)" column
                        for col in columns:
                            col_str = str(col).strip()
                            if col_str == '員工(姓名/ID)' or col_str == '員工姓名/ID':
                                logger.info(f"[TRACE] 員工(姓名/ID) column detected in sheet '{sheet_key}'")
                                employee_sheet = sheet_data
                                target_sheet_name = sheet_key
                                break
                        if employee_sheet:
                            break
            
            # PRIORITY 2: If not found, search all sheets for "員工(姓名/ID)" column
            if not employee_sheet:
                logger.info(f"[TRACE] Searching all sheets for '員工(姓名/ID)' column...")
                for sheet_name, sheet_data in sheets.items():
                    if isinstance(sheet_data, dict) and sheet_data.get('success') and sheet_data.get('data'):
                        columns = sheet_data.get('columns', [])
                        # Check if this sheet has the "員工(姓名/ID)" column (exact match first)
                        for col in columns:
                            col_str = str(col).strip()
                            if col_str == '員工(姓名/ID)' or col_str == '員工姓名/ID':
                                logger.info(f"[TRACE] 員工(姓名/ID) column detected in sheet '{sheet_name}'")
                                employee_sheet = sheet_data
                                target_sheet_name = sheet_name
                                break
                        if employee_sheet:
                            break
            
            if not employee_sheet or not employee_sheet.get('success'):
                logger.warning(f"[SYNC] No valid employee sheet found with '員工(姓名/ID)' column. Available sheets: {list(sheets.keys())}")
                return mappings_synced
            
            logger.info(f"[TRACE] Using sheet '{target_sheet_name}' for EmployeeMapping sync")
            
            employee_data = employee_sheet.get('data', [])
            employee_columns = employee_sheet.get('columns', [])
            
            if not employee_data or not employee_columns:
                logger.warning(f"[SYNC] No data in employee sheet. Data rows: {len(employee_data) if employee_data else 0}, Columns: {len(employee_columns) if employee_columns else 0}")
                return mappings_synced
            
            logger.info(f"[SYNC] Using sheet with {len(employee_data)} rows and {len(employee_columns)} columns for EmployeeMapping sync")
            logger.info(f"[TRACE][SYNC] Starting EmployeeMapping sync - will detect new, removed, and updated employees")
            
            # Get schedule definition for tenant_id
            schedule_def = ScheduleDefinition.query.get(schedule_def_id)
            if not schedule_def:
                logger.error(f"[SYNC] Schedule definition not found: {schedule_def_id}")
                return mappings_synced
            
            tenant_id = schedule_def.tenantID
            
            # Get current count of active employees in DB for this schedule (before sync)
            existing_count = EmployeeMapping.query.filter_by(
                schedule_def_id=schedule_def_id,
                is_active=True
            ).count()
            logger.info(f"[TRACE][SYNC] Current active employees in DB for schedule {schedule_def_id}: {existing_count}")
            
            # Find Employee ID column - EXACT MATCH for "員工(姓名/ID)" first (no English fallback)
            emp_id_column = None
            emp_name_column = None
            emp_name_id_column = None
            
            for col in employee_columns:
                col_str = str(col).strip()
                col_lower = col_str.lower()
                
                # PRIORITY 1: Exact match for "員工(姓名/ID)" (required format)
                if not emp_name_id_column:
                    if col_str == '員工(姓名/ID)' or col_str == '員工姓名/ID':
                        emp_name_id_column = col
                        logger.info(f"[TRACE] 員工(姓名/ID) column detected: '{col_str}'")
                        break  # Found exact match, stop searching
            
            # If exact match not found, try partial match (fallback)
            if not emp_name_id_column:
                for col in employee_columns:
                    col_str = str(col).strip()
                    if '員工(姓名/ID)' in col_str or '員工姓名/ID' in col_str:
                        emp_name_id_column = col
                        logger.info(f"[TRACE] Found Name/ID combined column (partial match): '{col_str}'")
                        break
                
                # PRIORITY 2: Check for dedicated Employee ID column (fallback only)
                if not emp_name_id_column:
                    for col in employee_columns:
                        col_str = str(col).strip()
                        col_lower = col_str.lower()
                        if (
                            '員工ID' in col_str or
                            '員工編號' in col_str or 
                            'employee id' in col_lower or 
                            'employee_id' in col_lower or
                            col_str == '員工編號' or
                            col_str == 'Employee ID'
                        ):
                            emp_id_column = col
                            logger.info(f"[TRACE] Found Employee ID column: '{col_str}'")
                            break
                
                # PRIORITY 3: Check for Employee Name column (fallback only)
                if not emp_name_id_column:
                    for col in employee_columns:
                        col_str = str(col).strip()
                        col_lower = col_str.lower()
                        if (
                            '姓名' in col_str or
                            '員工姓名' in col_str or
                            'employee name' in col_lower or
                            'employee_name' in col_lower or
                            (col_lower == 'name' and 'id' not in col_lower)
                        ):
                            emp_name_column = col
                            logger.info(f"[TRACE] Found Employee Name column: '{col_str}'")
                            break
            
            # If we found the combined column, we can extract both name and ID from it
            # Otherwise, we need at least an Employee ID column
            if not emp_name_id_column and not emp_id_column:
                logger.warning(f"[SYNC] Could not find Employee ID column in employee sheet. Available columns: {employee_columns}")
                logger.warning(f"[SYNC] Tried to match: '員工(姓名/ID)', '員工姓名/ID', '員工編號', 'Employee ID', 'employee_id'")
                return mappings_synced
            
            logger.info(f"[TRACE][SYNC] Found columns - Employee ID: '{emp_id_column}', Name: '{emp_name_column}', Name/ID combined: '{emp_name_id_column}'")
            
            if emp_name_id_column:
                logger.info(f"[TRACE] 員工(姓名/ID) column detected: '{emp_name_id_column}'")
            elif emp_id_column:
                logger.info(f"[TRACE] Employee ID column detected: '{emp_id_column}'")
            
            # Process each employee row row-by-row
            logger.info(f"[TRACE][SYNC] Processing {len(employee_data)} rows from employee sheet row-by-row...")
            for row_idx, row in enumerate(employee_data, start=1):
                if not isinstance(row, dict):
                    logger.debug(f"[SYNC] Row {row_idx}: Skipping non-dict row")
                    continue
                
                emp_id = None
                emp_name = None
                emp_name_id = None
                
                # PRIORITY 1: Extract from combined "員工(姓名/ID)" column (e.g., "謝○穎/E01")
                if emp_name_id_column:
                    name_id_value = row.get(emp_name_id_column, '')
                    if name_id_value:
                        name_id_str = str(name_id_value).strip()
                        if '/' in name_id_str:
                            # Split by '/' to get name (left side) and ID (right side)
                            parts = name_id_str.split('/', 1)  # Split only on first '/'
                            if len(parts) == 2:
                                emp_name = parts[0].strip()  # Left side = name
                                emp_id_raw = parts[1].strip()  # Right side = employee_id
                                emp_id = emp_id_raw.upper()  # Normalize to uppercase
                                emp_name_id = name_id_str  # Full format
                                
                                # Validate employee_id matches pattern [A-Z]\d{2,3}
                                if not re.match(r'^[A-Z]\d{2,3}$', emp_id):
                                    logger.warning(f"[TRACE] Row {row_idx}: Extracted employee_id '{emp_id}' doesn't match pattern [A-Z]\\d{{2,3}}, skipping row")
                                    continue
                                
                                logger.info(f"[TRACE] Extracted employee_id={emp_id} for {emp_name}")
                                logger.debug(f"[SYNC] ✅ Row {row_idx}: Parsed from '員工(姓名/ID)' column: name='{emp_name}', id='{emp_id}', full='{emp_name_id}'")
                            else:
                                # Invalid format - skip this row
                                logger.warning(f"[SYNC] Row {row_idx}: Invalid Name/ID format (expected 'name/id'): '{name_id_str}', skipping row")
                                continue
                        else:
                            # No '/' found - try to use entire value as ID if it matches pattern
                            name_id_str_upper = name_id_str.upper()
                            if re.match(r'^[A-Z]\d{2,3}$', name_id_str_upper):
                                # Entire value is an employee_id (e.g., "E01")
                                emp_id = name_id_str_upper
                                emp_name_id = name_id_str
                                logger.debug(f"[SYNC] Row {row_idx}: Using entire value as ID (no '/'): '{emp_id}'")
                            else:
                                logger.warning(f"[SYNC] Row {row_idx}: Name/ID column value has no '/' and doesn't match employee_id pattern: '{name_id_str}', skipping row")
                                continue
                
                # PRIORITY 2: If we don't have ID yet, try dedicated Employee ID column
                if not emp_id and emp_id_column:
                    emp_id_raw = row.get(emp_id_column) or row.get("員工編號") or row.get("Employee ID") or row.get("employee_id")
                    if emp_id_raw:
                        emp_id = str(emp_id_raw).strip().upper()
                        # Validate employee_id pattern
                        if not re.match(r'^[A-Z]\d{2,3}$', emp_id):
                            logger.warning(f"[TRACE] Row {row_idx}: Employee ID '{emp_id}' doesn't match pattern [A-Z]\\d{{2,3}}, skipping row")
                            continue
                
                # If still no ID found, skip this row
                if not emp_id:
                    logger.debug(f"[SYNC] Row {row_idx}: No Employee ID found, skipping. Row keys: {list(row.keys())[:5]}")
                    continue
                
                # Final validation: ensure employee_id matches pattern
                if not re.match(r'^[A-Z]\d{2,3}$', emp_id):
                    logger.warning(f"[TRACE] Row {row_idx}: Final employee_id '{emp_id}' doesn't match pattern [A-Z]\\d{{2,3}}, skipping row")
                    continue
                
                # Extract employee name if not already extracted
                if not emp_name:
                    if emp_name_column:
                        emp_name = str(row.get(emp_name_column, '')).strip()
                    elif emp_name_id:
                        # Already extracted from name/ID column
                        pass
                
                # FALLBACK: If we have separate 員工ID and 姓名 columns, reconstruct the mapping
                if not emp_name_id and emp_id and emp_name:
                    emp_name_id = f"{emp_name}/{emp_id}"
                    logger.info(f"[TRACE] Reconstructed name/ID from separate columns: '{emp_name_id}'")
                
                # Ensure emp_name_id is set if we have both name and ID
                if not emp_name_id and emp_name and emp_id:
                    emp_name_id = f"{emp_name}/{emp_id}"
                
                # Track this employee ID as found in sheet
                employees_in_sheet.add(emp_id.upper())
                
                # Try to link to existing User by employee_id
                # This ensures EmployeeMapping is linked to User if user exists
                linked_user = None
                if emp_id:
                    # Try to find user by employee_id
                    user_by_employee_id = User.query.filter(
                        User.employee_id == emp_id,
                        User.status == 'active'
                    ).first()
                    
                    # Also try to find user by username (for employees, username = employee_id)
                    if not user_by_employee_id:
                        user_by_username = User.query.filter(
                            User.username == emp_id,
                            User.status == 'active'
                        ).first()
                        if user_by_username:
                            linked_user = user_by_username
                            # Update user.employee_id if missing
                            if not user_by_username.employee_id:
                                user_by_username.employee_id = emp_id
                                logger.info(f"[TRACE] Matched DB user for {emp_id} (by username), updated employee_id")
                    else:
                        linked_user = user_by_employee_id
                        logger.info(f"[TRACE] Matched DB user for {emp_id} (by employee_id)")
                
                # Check if EmployeeMapping already exists for this sheets_identifier and schedule_def_id
                # First check for exact match (same schedule_def_id)
                existing_mapping = EmployeeMapping.query.filter_by(
                    sheets_identifier=emp_id,
                    schedule_def_id=schedule_def_id,
                    is_active=True
                ).first()
                
                # If not found, check if there's a mapping with same sheets_identifier but different schedule_def_id
                # (for cases where employee appears in multiple schedules)
                if not existing_mapping:
                    existing_mapping = EmployeeMapping.query.filter_by(
                        sheets_identifier=emp_id,
                        tenantID=tenant_id,
                        is_active=True
                    ).first()
                
                if existing_mapping:
                    # Update existing mapping if needed
                    # Only update if it's for the same schedule_def_id, or if it has no schedule_def_id
                    should_update = (
                        existing_mapping.schedule_def_id == schedule_def_id or
                        existing_mapping.schedule_def_id is None
                    )
                    
                    if should_update:
                        # Update schedule_def_id if it was None
                        if existing_mapping.schedule_def_id is None:
                            existing_mapping.schedule_def_id = schedule_def_id
                        
                        # Link to user if not already linked and we found a matching user
                        if linked_user and not existing_mapping.userID:
                            existing_mapping.userID = linked_user.userID
                            logger.info(f"[TRACE] Linked EmployeeMapping {emp_id} to user {linked_user.username}")
                        
                        # Track name changes for logging
                        name_changed = False
                        old_name = existing_mapping.employee_sheet_name
                        
                        # Update name fields if they've changed
                        if emp_name_id and existing_mapping.sheets_name_id != emp_name_id:
                            existing_mapping.sheets_name_id = emp_name_id
                            name_changed = True
                        if emp_name and existing_mapping.employee_sheet_name != emp_name:
                            existing_mapping.employee_sheet_name = emp_name
                            name_changed = True
                        
                        if name_changed:
                            employees_updated.append({
                                'id': emp_id,
                                'old_name': old_name,
                                'new_name': emp_name or existing_mapping.employee_sheet_name
                            })
                            logger.info(f"[TRACE][SYNC] Employee name updated: {emp_id} → {emp_name or existing_mapping.employee_sheet_name} (was: {old_name})")
                        
                        existing_mapping.updated_at = datetime.utcnow()
                        # Ensure is_active is True (in case it was previously marked inactive)
                        if not existing_mapping.is_active:
                            existing_mapping.is_active = True
                            logger.info(f"[TRACE][SYNC] Employee reactivated: {emp_id} (was previously inactive)")
                        db.session.merge(existing_mapping)
                        mappings_synced += 1
                        logger.debug(f"[SYNC] Updated EmployeeMapping: {emp_id}")
                    else:
                        # Mapping exists for different schedule - create new one for this schedule
                        # But only if userID is None (not linked to a user)
                        if existing_mapping.userID is None:
                            try:
                                new_mapping = EmployeeMapping(
                                    tenantID=tenant_id,
                                    sheets_identifier=emp_id,  # Employee ID (e.g., "E01", "E03")
                                    sheets_name_id=emp_name_id,  # Full format (e.g., "謝○穎/E01")
                                    employee_sheet_name=emp_name,  # Employee name (e.g., "謝○穎")
                                    schedule_def_id=schedule_def_id,
                                    userID=None,  # Not linked to any user yet - available for registration
                                    is_active=True
                                )
                                db.session.add(new_mapping)
                                mappings_synced += 1
                                employees_added.append({'id': emp_id, 'name': emp_name or emp_id})
                                logger.info(f"[SYNC] ✅ Row {row_idx}: Created EmployeeMapping for schedule {schedule_def_id}: sheets_identifier='{emp_id}', name='{emp_name}', full='{emp_name_id}'")
                            except Exception as e:
                                logger.error(f"[SYNC] Failed to create EmployeeMapping for {emp_id}: {e}")
                                db.session.rollback()
                                continue
                else:
                    # Create new EmployeeMapping (link to user if found)
                    try:
                        new_mapping = EmployeeMapping(
                            tenantID=tenant_id,
                            sheets_identifier=emp_id,  # Employee ID (e.g., "E01", "E03")
                            sheets_name_id=emp_name_id,  # Full format (e.g., "謝○穎/E01")
                            employee_sheet_name=emp_name,  # Employee name (e.g., "謝○穎")
                            schedule_def_id=schedule_def_id,
                            userID=linked_user.userID if linked_user else None,  # Link to user if found
                            is_active=True
                        )
                        db.session.add(new_mapping)
                        mappings_synced += 1
                        employees_added.append({'id': emp_id, 'name': emp_name or emp_id})
                        if linked_user:
                            logger.info(f"[TRACE] Matched DB user for {emp_id}")
                        logger.info(f"[TRACE][SYNC] New employee added from sheet: {emp_id} ({emp_name or emp_id})")
                        logger.info(f"[SYNC] ✅ Row {row_idx}: Created EmployeeMapping: sheets_identifier='{emp_id}', name='{emp_name}', full='{emp_name_id}'")
                    except Exception as e:
                        logger.error(f"[SYNC] Row {row_idx}: Failed to create EmployeeMapping for {emp_id}: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        db.session.rollback()
                        continue
            
            # After processing all rows, check for employees in DB that are missing from sheet
            # Mark them as inactive (but don't delete - they may be linked to users)
            logger.info(f"[TRACE][SYNC] Checking for employees removed from sheet (found {len(employees_in_sheet)} in sheet)...")
            db_employees = EmployeeMapping.query.filter_by(
                schedule_def_id=schedule_def_id,
                is_active=True
            ).all()
            
            for db_emp in db_employees:
                emp_id_upper = db_emp.sheets_identifier.upper()
                if emp_id_upper not in employees_in_sheet:
                    # Employee exists in DB but not in sheet - mark as inactive
                    db_emp.is_active = False
                    db_emp.updated_at = datetime.utcnow()
                    employees_removed.append({
                        'id': db_emp.sheets_identifier,
                        'name': db_emp.employee_sheet_name or db_emp.sheets_identifier
                    })
                    logger.info(f"[TRACE][SYNC] Employee removed from sheet: {db_emp.sheets_identifier} ({db_emp.employee_sheet_name or db_emp.sheets_identifier}) (marked inactive)")
                    mappings_synced += 1
            
            # Commit all EmployeeMapping changes in a single transaction
            try:
                db.session.commit()
                
                # Log summary of changes
                logger.info(f"[TRACE][SYNC] ========== EMPLOYEE MAPPING SYNC SUMMARY ==========")
                new_count = EmployeeMapping.query.filter_by(
                    schedule_def_id=schedule_def_id,
                    is_active=True
                ).count()
                logger.info(f"[TRACE][SYNC] Total employees in DB: {new_count} (previously {existing_count})")
                
                if employees_added:
                    logger.info(f"[TRACE][SYNC] ✅ Parsed {len(employees_added)} new employee IDs from Google Sheets")
                    emp_ids_list = [e['id'] for e in employees_added]
                    logger.info(f"[TRACE][SYNC] New IDs: {', '.join(emp_ids_list)}")
                    logger.info(f"[TRACE] Parsed {len(employees_added)} employees: {', '.join(emp_ids_list)}")
                    for emp in employees_added:
                        logger.info(f"[TRACE][SYNC]   - Added: {emp['id']} ({emp['name']})")
                
                if employees_updated:
                    logger.info(f"[TRACE][SYNC] ✅ Updated {len(employees_updated)} employee names")
                    for emp in employees_updated:
                        logger.info(f"[TRACE][SYNC]   - Updated: {emp['id']} → {emp['new_name']} (was: {emp['old_name']})")
                
                if employees_removed:
                    logger.info(f"[TRACE][SYNC] ✅ Marked {len(employees_removed)} employees as inactive")
                    for emp in employees_removed:
                        logger.info(f"[TRACE][SYNC]   - Removed: {emp['id']} ({emp['name']})")
                
                if not employees_added and not employees_updated and not employees_removed:
                    logger.info(f"[TRACE][SYNC] ✅ No changes detected - all employees up to date")
                
                # Count matched users
                matched_users_count = EmployeeMapping.query.filter_by(
                    schedule_def_id=schedule_def_id,
                    is_active=True
                ).filter(EmployeeMapping.userID.isnot(None)).count()
                
                logger.info(f"[TRACE] Users matched: {matched_users_count}")
                logger.info(f"[TRACE][SYNC] ==================================================")
                logger.info(f"[SYNC] ✅ Successfully synced {mappings_synced} EmployeeMapping records from employee sheet (committed to database)")
                logger.info(f"[TRACE] Schedule sync complete for {len(employees_in_sheet)} employees")
            except Exception as e:
                logger.error(f"[SYNC] Failed to commit EmployeeMapping changes: {e}")
                db.session.rollback()
                import traceback
                logger.error(traceback.format_exc())
                return 0
            
        except Exception as e:
            logger.error(f"[SYNC] Error syncing EmployeeMapping records: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
        
        return mappings_synced
    
    def _link_users_to_employee_mappings(self, schedule_def_id: str, auto_create_users: bool = True) -> int:
        """
        Link User records to EmployeeMapping records based on employee_id matching
        Optionally auto-creates missing users if they don't exist.
        
        This function:
        1. Finds all EmployeeMappings without linked users
        2. Tries to match them with Users by username or employee_id
        3. Auto-creates users if missing (if auto_create_users=True)
        4. Updates User.employee_id if missing
        5. Links EmployeeMapping.userID to User.userID
        6. Ensures tenantID matches
        
        Args:
            schedule_def_id: Schedule definition ID
            auto_create_users: If True, auto-create missing users (default: True)
            
        Returns:
            Number of users linked/created
        """
        users_linked = 0
        users_created = 0
        
        try:
            # Get schedule definition for tenant
            schedule_def = ScheduleDefinition.query.get(schedule_def_id)
            if not schedule_def:
                logger.error(f"[ERROR][SYNC] ScheduleDefinition not found: {schedule_def_id}")
                return 0
            
            # Get all EmployeeMappings without linked users (for this schedule or any schedule in same tenant)
            unmapped_employees = EmployeeMapping.query.filter(
                EmployeeMapping.tenantID == schedule_def.tenantID,
                EmployeeMapping.is_active == True,
                (EmployeeMapping.userID.is_(None)) | (EmployeeMapping.userID == '')
            ).all()
            
            logger.info(f"[TRACE][SYNC] Found {len(unmapped_employees)} EmployeeMappings without linked users")
            
            for mapping in unmapped_employees:
                emp_id = mapping.sheets_identifier.strip().upper()
                emp_name = mapping.employee_sheet_name or mapping.sheets_name_id or emp_id
                
                # Safety check: Skip if mapping is already linked (shouldn't happen due to query filter, but double-check)
                if mapping.userID:
                    linked_user = User.query.get(mapping.userID)
                    if linked_user and linked_user.status == 'active':
                        logger.debug(f"[TRACE][SYNC] EmployeeMapping {emp_id} already linked to user {linked_user.username}, skipping")
                        continue
                
                # Try to find user by employee_id or username
                user = User.query.filter(
                    ((User.employee_id == emp_id) | (User.username == emp_id)),
                    User.status == 'active'
                ).first()
                
                if not user and auto_create_users:
                    # Auto-create user if missing
                    logger.info(f"[AUTO_CREATE] Creating user for employee_id={emp_id} (name: {emp_name})")
                    
                    # Generate default password
                    default_password = "default@123"  # Should be changed on first login
                    
                    # Extract name from sheets_name_id if available
                    full_name = None
                    if emp_name and '/' not in str(emp_name):
                        full_name = str(emp_name).strip()
                    elif mapping.sheets_name_id and '/' in mapping.sheets_name_id:
                        full_name = mapping.sheets_name_id.split('/')[0].strip()
                    
                    # Create new user
                    user = User(
                        tenantID=mapping.tenantID,
                        username=emp_id,
                        password=default_password,  # Will be hashed in __init__
                        role='employee',
                        status='active',
                        employee_id=emp_id,
                        full_name=full_name
                    )
                    db.session.add(user)
                    db.session.flush()  # Get userID
                    users_created += 1
                    logger.info(f"[AUTO_CREATE] ✅ Created user {emp_id} (userID: {user.userID}, name: {full_name or 'N/A'})")
                
                if user:
                    # Link the mapping to the user
                    mapping.userID = user.userID
                    
                    # Ensure tenant matches
                    if mapping.tenantID != user.tenantID:
                        logger.warning(f"[TRACE][SYNC] Tenant mismatch for {emp_id}: mapping.tenantID={mapping.tenantID}, user.tenantID={user.tenantID}")
                        mapping.tenantID = user.tenantID
                    
                    # Update user.employee_id if missing
                    if not user.employee_id or user.employee_id.upper() != emp_id:
                        old_employee_id = user.employee_id
                        user.employee_id = emp_id
                        logger.info(f"[TRACE][SYNC] Updated user.employee_id for {user.username}: '{old_employee_id}' -> '{emp_id}'")
                    
                    users_linked += 1
                    logger.info(f"[TRACE] Matched DB user for {emp_id}: {user.username} (userID: {user.userID})")
                else:
                    logger.info(f"[TRACE][SYNC] No user found for employee_id '{emp_id}' (waiting for registration)")
            
            # Commit all changes
            if users_linked > 0 or users_created > 0:
                db.session.commit()
                if users_created > 0:
                    logger.info(f"[AUTO_FIX] ✅ Created {users_created} missing employee users")
                logger.info(f"[TRACE][SYNC] ✅ Linked {users_linked} users to EmployeeMappings")
            
        except Exception as e:
            logger.error(f"[ERROR][SYNC] Error linking users to EmployeeMappings: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
        
        return users_linked + users_created
    
    def _store_schedule_data(self, schedule_def_id: str, sheets_data: Dict[str, Any]) -> tuple:
        """
        Store schedule data from Google Sheets to database
        
        IMPORTANT: This function:
        1. Fetches ALL rows from Google Sheets (regardless of user registration)
        2. Extracts employee_id from "姓名/ID" format (e.g., "謝○穎/E01" -> "E01")
        3. Matches with username in database
        4. Saves schedule data to CachedSchedule if user exists
        5. Creates EmployeeMapping if user doesn't exist yet (for future registration)
        """
        """
        Parse and store schedule data in database
        
        Args:
            schedule_def_id: Schedule definition ID
            sheets_data: Data from Google Sheets
            
        Returns:
            Tuple of (rows_synced, users_synced)
        """
        rows_synced = 0
        users_synced = 0
        
        sheets = sheets_data.get('sheets', {})
        final_output = sheets.get('final_output', {})
        
        if not final_output.get('success'):
            logger.warning(f"[SYNC] Final output sheet not available")
            return rows_synced, users_synced
        
        output_data = final_output.get('data', [])
        output_columns = final_output.get('columns', [])
        
        if not output_data or not output_columns:
            logger.warning(f"[SYNC] No data in final output sheet")
            return rows_synced, users_synced
        
        # Get all users with employee mappings for this schedule
        employee_mappings = EmployeeMapping.query.filter_by(
            schedule_def_id=schedule_def_id,
            is_active=True
        ).all()
        
        # Also get all users with employee_id set (for consistency)
        # Note: User is already imported at module level
        users_with_employee_id = User.query.filter(
            User.employee_id.isnot(None),
            User.status == 'active'
        ).all()
        
        # Create a mapping of sheets_identifier/employee_id -> user_id
        # CRITICAL: Use a dictionary that prevents duplicate mappings
        identifier_to_user = {}
        mapping_conflicts = []
        
        for mapping in employee_mappings:
            if mapping.userID:  # Only map if linked to a user
                # Map by sheets_identifier (employee_id) - this is the primary key
                identifier_upper = mapping.sheets_identifier.upper().strip()
                
                # Check for conflicts - if same identifier maps to different user_id
                if identifier_upper in identifier_to_user:
                    existing_user_id = identifier_to_user[identifier_upper]
                    if existing_user_id != mapping.userID:
                        conflict_msg = f"CONFLICT: employee_id '{mapping.sheets_identifier}' maps to both user_id {existing_user_id} and {mapping.userID}"
                        mapping_conflicts.append(conflict_msg)
                        logger.error(f"[ERROR][SYNC] {conflict_msg}")
                        # Use the most recent mapping (or could use EmployeeMapping with latest updated_at)
                        # For now, keep the first one and log the conflict
                    else:
                        # Same mapping, no conflict
                        pass
                else:
                    identifier_to_user[identifier_upper] = mapping.userID
                    logger.debug(f"[TRACE][SYNC] Mapped employee_code '{mapping.sheets_identifier}' -> user_id '{mapping.userID}'")
                
                if mapping.sheets_name_id:
                    # Also map the full name/ID format
                    full_name_id = str(mapping.sheets_name_id).strip()
                    if full_name_id and full_name_id not in identifier_to_user:
                        identifier_to_user[full_name_id] = mapping.userID
                    elif full_name_id in identifier_to_user and identifier_to_user[full_name_id] != mapping.userID:
                        conflict_msg = f"CONFLICT: full identifier '{full_name_id}' maps to both user_id {identifier_to_user[full_name_id]} and {mapping.userID}"
                        mapping_conflicts.append(conflict_msg)
                        logger.error(f"[ERROR][SYNC] {conflict_msg}")
                    
                    # Map parts if it contains '/' - but be careful not to create false matches
                    if '/' in mapping.sheets_name_id:
                        parts = mapping.sheets_name_id.split('/')
                        for part in parts:
                            part_clean = part.strip().upper()
                            if part_clean and len(part_clean) >= 2:
                                # Only map if it looks like an employee_id (E01, N01, etc.)
                                if part_clean[0].isalpha() and part_clean[1:].isdigit():
                                    if part_clean not in identifier_to_user:
                                        identifier_to_user[part_clean] = mapping.userID
                                    elif identifier_to_user[part_clean] != mapping.userID:
                                        conflict_msg = f"CONFLICT: part '{part_clean}' from '{mapping.sheets_name_id}' maps to both user_id {identifier_to_user[part_clean]} and {mapping.userID}"
                                        mapping_conflicts.append(conflict_msg)
                                        logger.error(f"[ERROR][SYNC] {conflict_msg}")
        
        if mapping_conflicts:
            logger.error(f"[ERROR][SYNC] Found {len(mapping_conflicts)} mapping conflicts - this may cause incorrect schedule assignments!")
            for conflict in mapping_conflicts[:5]:  # Log first 5 conflicts
                logger.error(f"[ERROR][SYNC] {conflict}")
        
        # Also map by User.employee_id for direct matching (backup)
        for user in users_with_employee_id:
            if user.employee_id:
                employee_id_upper = user.employee_id.upper()
                if employee_id_upper not in identifier_to_user:
                    identifier_to_user[employee_id_upper] = user.userID
                    logger.debug(f"[TRACE][SYNC] Mapped user.employee_id '{user.employee_id}' -> user_id '{user.userID}'")
        
        # CRITICAL: For employees, username IS the employee_id, so map username to user_id
        # This ensures new employees can match their schedule by username
        all_users = User.query.filter(User.status == 'active').all()
        for user in all_users:
            if user.username:
                username_upper = str(user.username).strip().upper()
                # For employee role, username IS the employee_id - always map it
                if user.role and user.role.lower() == 'employee':
                    if username_upper not in identifier_to_user:
                        identifier_to_user[username_upper] = user.userID
                        logger.info(f"[TRACE][SYNC] Mapped employee username '{user.username}' -> user_id '{user.userID}'")
                    # Also map employee_id if it's different from username
                    if user.employee_id:
                        emp_id_upper = str(user.employee_id).strip().upper()
                        if emp_id_upper != username_upper and emp_id_upper not in identifier_to_user:
                            identifier_to_user[emp_id_upper] = user.userID
                            logger.info(f"[TRACE][SYNC] Mapped employee_id '{user.employee_id}' -> user_id '{user.userID}'")
                # Also map if username matches an employee_id pattern (E01, N01, etc.)
                elif len(username_upper) >= 2 and username_upper[0].isalpha() and username_upper[1:].isdigit():
                    if username_upper not in identifier_to_user:
                        identifier_to_user[username_upper] = user.userID
                        logger.debug(f"[TRACE][SYNC] Mapped username (employee_id pattern) '{user.username}' -> user_id '{user.userID}'")
        
        logger.info(f"[TRACE][SYNC] Created identifier mapping: {len(identifier_to_user)} entries")
        logger.info(f"[SYNC] Found {len(employee_mappings)} employee mappings and {len(users_with_employee_id)} users with employee_id")
        
        # Debug: Log some mappings
        sample_mappings = list(identifier_to_user.items())[:10]
        logger.info(f"[TRACE][SYNC] Sample identifier mappings: {sample_mappings}")
        
        # Find the employee identifier column - prioritize Chinese header "員工(姓名/ID)"
        identifier_column = None
        logger.info(f"[TRACE][SCHEDULE_SYNC] Searching for employee identifier column in {len(output_columns)} columns")
        
        # PRIORITY 1: Exact match for Chinese header "員工(姓名/ID)"
        for col in output_columns:
            col_str = str(col).strip()
            if col_str == '員工(姓名/ID)' or col_str == '員工姓名/ID':
                identifier_column = col
                logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Found exact match: '{col_str}'")
                break
        
        # PRIORITY 2: Partial match (contains both 員工 and ID)
        if not identifier_column:
            for col in output_columns:
                col_str = str(col).strip()
                if '員工' in col_str and ('ID' in col_str or 'id' in col_str or '姓名' in col_str):
                    identifier_column = col
                    logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Found partial match: '{col_str}'")
                    break
        
        # PRIORITY 3: Fallback to English headers
        if not identifier_column:
            for col in ['員工', 'username', 'employee_id', 'name', 'employee']:
                if col in output_columns:
                    identifier_column = col
                    logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Found fallback match: '{col}'")
                    break
        
        if not identifier_column:
            logger.error(f"[TRACE][SCHEDULE_SYNC] ❌ Could not find identifier column")
            logger.error(f"[TRACE][SCHEDULE_SYNC] Available columns: {output_columns[:10]}")
            logger.error(f"[TRACE][SCHEDULE_SYNC] Searched for: '員工(姓名/ID)', '員工姓名/ID', '員工', 'username', 'employee_id'")
            return rows_synced, users_synced
        
        logger.info(f"[TRACE][SCHEDULE_SYNC] Using identifier column: '{identifier_column}'")
        
        # Process each row
        synced_users = set()
        total_rows = len(output_data)
        logger.info(f"[TRACE][SYNC] Processing {total_rows} rows from Google Sheets Final Output")
        
        for row_idx, row in enumerate(output_data, 1):
            if not isinstance(row, dict):
                continue
            
            # Get employee identifier from column (e.g., "謝○穎/E01")
            identifier = row.get(identifier_column, '')
            if not identifier:
                continue
            
            identifier_str = str(identifier).strip()  # Keep original for logging
            identifier_upper = identifier_str.upper()  # Normalized for matching
            
            # CRITICAL: Extract employee_id from "姓名/ID" format
            # Format: "謝○穎/E01" -> extract employee_name="謝○穎", employee_id="E01"
            # The name part (before /) should be ignored for matching, only use the ID part (after /)
            employee_id_from_sheet = None
            employee_name_from_sheet = None
            
            # Normalize identifier: trim spaces, uppercase, remove invisible unicode chars
            identifier_normalized = ''.join(c for c in identifier_str if unicodedata.category(c)[0] != 'C' or c in ['/', '-', '_']).strip()
            
            if '/' in identifier_normalized:
                # Split by '/' and take the last part (the ID)
                parts = identifier_normalized.split('/')
                if len(parts) >= 2:
                    # Extract name (all parts except last) and ID (last part)
                    employee_name_from_sheet = '/'.join(parts[:-1]).strip()  # Name part(s)
                    id_part = parts[-1].strip().upper()  # ID part
                    
                    # Remove any invisible unicode characters from ID
                    id_part = ''.join(c for c in id_part if unicodedata.category(c)[0] != 'C' or c.isalnum()).strip()
                    
                    # Verify it looks like an employee_id (E01, N01, etc.)
                    if len(id_part) >= 2 and id_part[0].isalpha() and id_part[1:].isdigit():
                        employee_id_from_sheet = id_part
                        logger.info(f"[MATCHED] Row {row_idx}: '{identifier_str}' -> employee_id='{employee_id_from_sheet}', name='{employee_name_from_sheet}'")
                    else:
                        logger.warning(f"[UNMATCHED EMPLOYEE ID] Row {row_idx}: ID part '{id_part}' doesn't match pattern [A-Z]\\d{{2,3}} (from '{identifier_str}')")
                else:
                    # If only one part, check if it's already an employee_id
                    single_part = parts[0].strip().upper()
                    single_part = ''.join(c for c in single_part if unicodedata.category(c)[0] != 'C' or c.isalnum()).strip()
                    if len(single_part) >= 2 and single_part[0].isalpha() and single_part[1:].isdigit():
                        employee_id_from_sheet = single_part
                        logger.info(f"[MATCHED] Row {row_idx}: Single part '{employee_id_from_sheet}' is employee_id from '{identifier_str}'")
            else:
                # No '/' separator - check if entire string is employee_id
                identifier_clean = ''.join(c for c in identifier_upper if unicodedata.category(c)[0] != 'C' or c.isalnum()).strip()
                if len(identifier_clean) >= 2 and identifier_clean[0].isalpha() and identifier_clean[1:].isdigit():
                    employee_id_from_sheet = identifier_clean
                    logger.info(f"[MATCHED] Row {row_idx}: Entire identifier '{employee_id_from_sheet}' is employee_id")
                else:
                    logger.warning(f"[UNMATCHED EMPLOYEE ID] Row {row_idx}: Identifier '{identifier_str}' doesn't match expected format (no '/' and not employee_id pattern)")
            
            # Find matching user by extracted employee_id
            user_id = None
            match_strategy = None
            
            if employee_id_from_sheet:
                # Strategy 1: Match extracted employee_id with exact match in identifier_to_user mapping
                # This is the PRIMARY matching strategy - must be exact
                if employee_id_from_sheet in identifier_to_user:
                    user_id = identifier_to_user[employee_id_from_sheet]
                    user_obj = User.query.get(user_id) if user_id else None
                    user_display = f"{user_obj.username}" if user_obj else f"user_id={user_id}"
                    match_strategy = "Strategy 1: Exact employee_id match"
                    logger.info(f"[MATCHED] {employee_id_from_sheet} -> employee_id={user_id} (user: {user_display})")
                else:
                    logger.warning(f"[UNMATCHED EMPLOYEE ID] {employee_id_from_sheet} (from '{identifier_str}') - not found in mapping (ignored)")
                    logger.debug(f"[TRACE][SCHEDULE_SYNC] Available mappings (first 20): {list(identifier_to_user.items())[:20]}")
                    logger.debug(f"[TRACE][SCHEDULE_SYNC] Total mappings: {len(identifier_to_user)}")
            
            # Strategy 2: Fallback - try exact match with full identifier (for edge cases where full "姓名/ID" format is in mapping)
            if not user_id and identifier_upper in identifier_to_user:
                user_id = identifier_to_user[identifier_upper]
                match_strategy = "Strategy 2: Full identifier match"
                logger.info(f"[TRACE][SYNC] ✅ {match_strategy}: '{identifier_str}' -> user_id={user_id}")
            
            # Strategy 3: REMOVED - Partial matching was causing incorrect matches
            # Instead, try matching by extracting ID from full identifier format in mapping
            if not user_id and employee_id_from_sheet:
                # Look for mappings where the key contains the employee_id (but be careful with partial matches)
                # Only match if the key ends with the employee_id or is exactly the employee_id
                for key, uid in identifier_to_user.items():
                    key_upper = str(key).strip().upper()
                    # Only match if:
                    # 1. Key is exactly the employee_id, OR
                    # 2. Key ends with "/employee_id" (e.g., "姓名/E01" ends with "/E01")
                    if key_upper == employee_id_from_sheet:
                        user_id = uid
                        match_strategy = f"Strategy 3: Key exact match '{key}'"
                        logger.info(f"[TRACE][SYNC] ✅ {match_strategy} -> user_id={user_id}")
                        break
                    elif '/' in key_upper and key_upper.endswith('/' + employee_id_from_sheet):
                        user_id = uid
                        match_strategy = f"Strategy 3: Key ends with '/{employee_id_from_sheet}' from '{key}'"
                        logger.info(f"[TRACE][SYNC] ✅ {match_strategy} -> user_id={user_id}")
                        break
            
            # Strategy 4: Direct User table lookup (if not found in mapping)
            # This handles cases where EmployeeMapping exists but isn't linked yet
            if not user_id and employee_id_from_sheet:
                # Try to find user by username matching employee_id
                direct_user = User.query.filter(
                    (User.username == employee_id_from_sheet) | 
                    (User.username.upper() == employee_id_from_sheet.upper()),
                    User.status == 'active'
                ).first()
                
                if direct_user:
                    user_id = direct_user.userID
                    logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Strategy 4: Direct User lookup found user_id={user_id} for employee_id '{employee_id_from_sheet}'")
                    
                    # Auto-link EmployeeMapping if it exists but isn't linked
                    existing_mapping = EmployeeMapping.find_by_sheets_identifier(employee_id_from_sheet, schedule_def_id)
                    if existing_mapping and not existing_mapping.userID:
                        existing_mapping.userID = user_id
                        existing_mapping.tenantID = direct_user.tenantID
                        existing_mapping.updated_at = datetime.utcnow()
                        db.session.flush()
                        logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Auto-linked EmployeeMapping for '{employee_id_from_sheet}' to user_id={user_id}")
                    
                    # Ensure user.employee_id is set
                    if not direct_user.employee_id or direct_user.employee_id.upper() != employee_id_from_sheet:
                        direct_user.employee_id = employee_id_from_sheet
                        db.session.flush()
                        logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Set user.employee_id='{employee_id_from_sheet}' for user_id={user_id}")
            
            if not user_id:
                # User not registered yet, but we should still create/update EmployeeMapping
                # This allows the schedule data to be available when user registers
                logger.info(f"[TRACE][SCHEDULE_SYNC] Row {row_idx}/{total_rows}: No user found for employee_id '{employee_id_from_sheet}' (from '{identifier_str}')")
                logger.info(f"[TRACE][SCHEDULE_SYNC] Creating/updating EmployeeMapping for future registration...")
                
                # Create or update EmployeeMapping for this employee_id
                # This ensures the schedule data is ready when user registers
                if employee_id_from_sheet:
                    # Get tenant from schedule definition (ScheduleDefinition already imported at module level)
                    schedule_def_obj = ScheduleDefinition.query.get(schedule_def_id)
                    if not schedule_def_obj:
                        logger.error(f"[ERROR][SYNC] ScheduleDefinition not found: {schedule_def_id}")
                        continue
                    tenant_id = schedule_def_obj.tenantID
                    
                    if tenant_id:
                        # Check if EmployeeMapping already exists
                        existing_mapping = EmployeeMapping.find_by_sheets_identifier(
                            employee_id_from_sheet, 
                            schedule_def_id
                        )
                        
                        if existing_mapping:
                            # Update existing mapping with full identifier and name
                            updated = False
                            if not existing_mapping.sheets_name_id or existing_mapping.sheets_name_id != identifier_str:
                                existing_mapping.sheets_name_id = identifier_str
                                updated = True
                            if employee_name_from_sheet and existing_mapping.employee_sheet_name != employee_name_from_sheet:
                                existing_mapping.employee_sheet_name = employee_name_from_sheet
                                updated = True
                            if updated:
                                existing_mapping.updated_at = datetime.utcnow()
                                logger.info(f"[TRACE][SCHEDULE_SYNC] Updated EmployeeMapping for '{employee_id_from_sheet}' (name: '{employee_name_from_sheet}', full: '{identifier_str}')")
                        else:
                            # Create new EmployeeMapping (user not registered yet)
                            new_mapping = EmployeeMapping(
                                tenantID=tenant_id,
                                schedule_def_id=schedule_def_id,
                                sheets_identifier=employee_id_from_sheet,
                                sheets_name_id=identifier_str,
                                employee_sheet_name=employee_name_from_sheet,
                                userID=None,  # Will be linked when user registers
                                is_active=True
                            )
                            db.session.add(new_mapping)
                            logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Created EmployeeMapping for '{employee_id_from_sheet}' (name: '{employee_name_from_sheet}', full: '{identifier_str}') - ready for registration")
                        
                        db.session.flush()  # Flush to ensure EmployeeMapping is saved
                
                # Skip saving to CachedSchedule if user doesn't exist yet
                # The schedule will be synced when user registers and logs in
                logger.info(f"[TRACE][SCHEDULE_SYNC] Schedule data for '{employee_id_from_sheet}' will be synced when user registers")
                continue
            
            synced_users.add(user_id)
            
            # Update user.employee_id if missing (for consistency)
            user_obj = User.query.get(user_id)
            if user_obj and employee_id_from_sheet:
                if not user_obj.employee_id or user_obj.employee_id.upper() != employee_id_from_sheet:
                    old_employee_id = user_obj.employee_id
                    user_obj.employee_id = employee_id_from_sheet
                    logger.info(f"[TRACE][SCHEDULE_SYNC] Updated user.employee_id for {user_obj.username}: '{old_employee_id}' -> '{employee_id_from_sheet}'")
            
            # CRITICAL: Validate user_id before processing
            if not user_id:
                logger.error(f"[TRACE][SCHEDULE_SYNC] ERROR: user_id is None for employee_id '{employee_id_from_sheet}' (identifier: '{identifier_str}')")
                continue
            
            # Verify user exists and is active
            user_obj = User.query.get(user_id)
            if not user_obj:
                logger.error(f"[TRACE][SCHEDULE_SYNC] ERROR: User {user_id} not found in database for employee_id '{employee_id_from_sheet}'")
                continue
            
            if user_obj.status != 'active':
                logger.warning(f"[TRACE][SCHEDULE_SYNC] WARNING: User {user_id} (employee_id: {employee_id_from_sheet}) is not active, skipping schedule sync")
                continue
            
            # Verify employee_id matches
            if employee_id_from_sheet and user_obj.employee_id:
                if user_obj.employee_id.upper() != employee_id_from_sheet.upper():
                    logger.warning(f"[TRACE][SCHEDULE_SYNC] WARNING: User {user_id} has employee_id '{user_obj.employee_id}' but sheet has '{employee_id_from_sheet}' - updating user.employee_id")
                    user_obj.employee_id = employee_id_from_sheet
            
            # CRITICAL: Log the match details for debugging
            logger.info(f"[TRACE][SCHEDULE_SYNC] ========== ROW {row_idx}/{total_rows} MATCHING ==========")
            logger.info(f"[TRACE][SCHEDULE_SYNC] Identifier from sheet: '{identifier_str}'")
            logger.info(f"[TRACE][SCHEDULE_SYNC] Extracted employee_id: '{employee_id_from_sheet}'")
            logger.info(f"[TRACE][SCHEDULE_SYNC] Matched user_id: {user_id}")
            logger.info(f"[TRACE][SCHEDULE_SYNC] Match strategy: {match_strategy}")
            logger.info(f"[TRACE][SCHEDULE_SYNC] User details: username={user_obj.username}, employee_id={user_obj.employee_id}")
            logger.info(f"[TRACE][SCHEDULE_SYNC] ==========================================")
            
            # Process date columns (skip identifier column)
            date_columns = [col for col in output_columns if col != identifier_column]
            logger.debug(f"[TRACE][SYNC] Found {len(date_columns)} date columns for user {user_id}")
            
            # Clear existing data for this user first (only for this specific user_id)
            cleared_count = CachedSchedule.clear_user_schedule(user_id, schedule_def_id)
            if cleared_count > 0:
                logger.info(f"[TRACE][SYNC] Cleared {cleared_count} existing schedule entries for user_id={user_id} (employee_id={employee_id_from_sheet})")
            
            # Process each date column
            dates_processed = 0
            for date_col in date_columns:
                try:
                    # Parse date from column header
                    date_obj = self._parse_date(date_col)
                    if not date_obj:
                        logger.debug(f"[TRACE][SYNC] Could not parse date from column '{date_col}', skipping")
                        continue
                    
                    # Get shift value - CRITICAL: Store EXACT value from sheet
                    shift_value_raw = row.get(date_col, '')
                    if shift_value_raw is None:
                        # Blank cell = OFF day
                        shift_value = 'OFF'
                        shift_type = 'OFF'
                        time_range = '休假'
                        logger.info(f"[TRACE][SCHEDULE_SYNC] Storing schedule: {employee_id_from_sheet} {date_obj} -> 'OFF' (blank cell)")
                    else:
                        shift_value_raw = str(shift_value_raw).strip()
                        # Empty or whitespace-only cells = OFF day
                        if not shift_value_raw or shift_value_raw == '' or shift_value_raw.upper() == 'NULL' or shift_value_raw.upper() == 'NONE':
                            shift_value = 'OFF'
                            shift_type = 'OFF'
                            time_range = '休假'
                            logger.info(f"[TRACE][SCHEDULE_SYNC] Storing schedule: {employee_id_from_sheet} {date_obj} -> 'OFF' (empty cell)")
                        else:
                            # Store the EXACT value from the sheet (no normalization)
                            # This preserves values like "C 櫃台人力", "B 二線人力", "A 藥局人力"
                            shift_value = shift_value_raw
                            
                            # Normalize shift type for internal use (optional, for time_range calculation)
                            shift_type = self._normalize_shift_type(shift_value_raw)
                            time_range = self._get_time_range(shift_type)
                            
                            # Log the shift value being stored
                            logger.info(f"[TRACE][SCHEDULE_SYNC] Storing schedule: {employee_id_from_sheet} {date_obj} -> '{shift_value}' (normalized: {shift_type})")
                    
                    # Get tenant_id from schedule definition or user (both already imported at module level)
                    schedule_def_obj = ScheduleDefinition.query.get(schedule_def_id)
                    if not schedule_def_obj:
                        logger.error(f"[ERROR][SYNC] ScheduleDefinition not found: {schedule_def_id}")
                        continue
                    
                    # CRITICAL: Re-verify user_id is still valid (user_obj was set earlier in the loop)
                    if not user_obj or user_obj.userID != user_id:
                        user_obj = User.query.get(user_id)
                        if not user_obj:
                            logger.error(f"[ERROR][SYNC] User {user_id} not found when storing schedule entry")
                            continue
                    
                    tenant_id = schedule_def_obj.tenantID if schedule_def_obj else (user_obj.tenantID if user_obj else None)
                    
                    # CRITICAL: Validate tenant_id matches user's tenant
                    if user_obj.tenantID != tenant_id:
                        logger.error(f"[ERROR][SYNC] Tenant mismatch: user.tenantID={user_obj.tenantID}, schedule_def.tenantID={tenant_id}")
                        continue
                    
                    # Store in database - CRITICAL: Ensure user_id is correct
                    # Double-check user_id is still correct (shouldn't change, but be safe)
                    current_user_id_for_entry = user_id  # Store in local variable to prevent any scope issues
                    
                    # Handle OFF days (blank cells) - create entry immediately
                    if shift_value == 'OFF' and shift_type == 'OFF':
                        schedule_entry = CachedSchedule(
                            tenant_id=tenant_id,
                            schedule_def_id=schedule_def_id,
                            user_id=current_user_id_for_entry,  # CRITICAL: Must match the employee_id from this row
                            date=date_obj,
                            shift_type='OFF',
                            shift_value='OFF',
                            time_range='休假'
                        )
                        db.session.merge(schedule_entry)
                        rows_synced += 1
                        dates_processed += 1
                        logger.info(f"[UPDATED SCHEDULE] {employee_id_from_sheet} {date_obj} -> 'OFF'")
                        # Commit per user after processing all dates for that user (OFF entries included)
                        if dates_processed % 10 == 0:  # Commit every 10 entries to avoid large transactions
                            db.session.commit()
                        continue  # Skip to next date
                    
                    # For non-OFF entries, create normal schedule entry
                    schedule_entry = CachedSchedule(
                        tenant_id=tenant_id,
                        schedule_def_id=schedule_def_id,
                        user_id=current_user_id_for_entry,  # CRITICAL: Must match the employee_id from this row
                        date=date_obj,
                        shift_type=shift_type,  # Normalized (D, E, N, OFF) for internal use
                        shift_value=shift_value,  # CRITICAL: Store EXACT value from sheet (e.g., "C 櫃台人力")
                        time_range=time_range
                    )
                    
                    # CRITICAL: Validate before saving - ensure user_id matches the employee_id from this row
                    if schedule_entry.user_id != current_user_id_for_entry:
                        logger.error(f"[ERROR][SYNC] Schedule entry user_id mismatch: {schedule_entry.user_id} != {current_user_id_for_entry} (employee_id={employee_id_from_sheet})")
                        continue
                    
                    # Additional validation: Verify the user_id belongs to the correct employee_id
                    entry_user = User.query.get(current_user_id_for_entry)
                    if entry_user:
                        expected_employee_id = employee_id_from_sheet.upper()
                        actual_employee_id = (entry_user.employee_id or entry_user.username or '').upper()
                        if expected_employee_id != actual_employee_id:
                            logger.warning(f"[WARNING][SYNC] Employee ID mismatch when storing: expected '{expected_employee_id}' but user has '{actual_employee_id}' (user_id={current_user_id_for_entry})")
                            # Still store it, but log the warning
                    
                    db.session.merge(schedule_entry)
                    rows_synced += 1
                    dates_processed += 1
                    
                    # Log every schedule update
                    logger.info(f"[UPDATED SCHEDULE] {employee_id_from_sheet} {date_obj} -> '{shift_value}'")
                    
                    # Log every 10th entry for debugging
                    if dates_processed % 10 == 0:
                        logger.debug(f"[TRACE][SYNC] Stored {dates_processed} entries so far for user_id={current_user_id_for_entry} (employee_id={employee_id_from_sheet})")
                    
                except Exception as e:
                    logger.warning(f"[SYNC] Error processing date column {date_col} for user {user_id}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    continue
            
            # CRITICAL: Commit after processing each user's schedule to ensure data is persisted
            # This prevents data loss if sync is interrupted
            if dates_processed > 0:
                try:
                    db.session.commit()
                    logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Committed {dates_processed} schedule entries for {employee_id_from_sheet} (user_id={current_user_id_for_entry})")
                except Exception as commit_error:
                    logger.error(f"[ERROR][SCHEDULE_SYNC] Failed to commit schedule entries for {employee_id_from_sheet}: {commit_error}")
                    db.session.rollback()
                    continue
            
            if dates_processed > 0:
                # Get employee name for logging
                emp_name = None
                if employee_name_from_sheet:
                    emp_name = employee_name_from_sheet
                elif user_obj:
                    mapping = EmployeeMapping.find_by_sheets_identifier(employee_id_from_sheet, schedule_def_id)
                    if mapping and mapping.employee_sheet_name:
                        emp_name = mapping.employee_sheet_name
                
                if emp_name:
                    logger.info(f"[TRACE][SCHEDULE_SYNC] Synced schedule for {employee_id_from_sheet} - {emp_name}: {dates_processed} entries")
                else:
                    logger.info(f"[TRACE][SYNC] Saved {dates_processed} schedule entries for user {user_id} (identifier: '{identifier_str}')")
        
        # CRITICAL: Final commit to ensure all changes are persisted
        # This commit happens BEFORE the function returns, ensuring data is saved
        try:
            db.session.commit()
            logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Final database commit successful: {rows_synced} entries committed")
        except Exception as commit_error:
            logger.error(f"[ERROR][SCHEDULE_SYNC] Final database commit failed: {commit_error}")
            db.session.rollback()
            raise  # Re-raise to ensure Celery task knows about the failure
        
        users_synced = len(synced_users)
        logger.info(f"[TRACE][SCHEDULE_SYNC] ✅ Schedule sync complete: {rows_synced} entries stored for {users_synced} users")
        logger.info(f"[SYNC] Stored {rows_synced} schedule entries for {users_synced} users")
        
        # CRITICAL: Verify schedules were stored with correct user_id
        logger.info(f"[TRACE][SCHEDULE_SYNC] ========== VERIFICATION ==========")
        for synced_user_id in synced_users:
            user_obj = User.query.get(synced_user_id)
            if user_obj:
                # Count schedules stored for this user
                stored_count = CachedSchedule.query.filter_by(
                    user_id=synced_user_id,
                    schedule_def_id=schedule_def_id
                ).count()
                logger.info(f"[TRACE][SCHEDULE_SYNC] User {user_obj.username} (user_id={synced_user_id}, employee_id={user_obj.employee_id}): {stored_count} schedule entries stored")
                
                # Verify no schedules were stored with wrong user_id (check for other users' employee_ids)
                if user_obj.employee_id:
                    # Check if any schedules exist with this user_id but wrong employee_id pattern
                    # This is a sanity check
                    all_user_schedules = CachedSchedule.query.filter_by(
                        user_id=synced_user_id,
                        schedule_def_id=schedule_def_id
                    ).all()
                    if all_user_schedules:
                        sample_dates = [s.date.isoformat() for s in all_user_schedules[:3]]
                        logger.debug(f"[TRACE][SCHEDULE_SYNC] Sample dates for {user_obj.username}: {sample_dates}")
        logger.info(f"[TRACE][SCHEDULE_SYNC] =================================")
        
        # Log which users were synced with their employee IDs and names
        if synced_users:
            user_details = []
            for uid in list(synced_users)[:10]:
                user_obj = User.query.get(uid)
                if user_obj:
                    emp_id = user_obj.employee_id or user_obj.username
                    # Get employee name from mapping
                    mapping = EmployeeMapping.find_by_sheets_identifier(emp_id, schedule_def_id)
                    emp_name = None
                    if mapping and mapping.employee_sheet_name:
                        emp_name = mapping.employee_sheet_name
                    if emp_name:
                        user_details.append(f"{emp_id} - {emp_name}")
                    else:
                        user_details.append(f"{user_obj.username} ({emp_id})")
                else:
                    user_details.append(f"user_id={uid}")
            
            logger.info(f"[TRACE][SCHEDULE_SYNC] Synced schedules for: {', '.join(user_details)}{'...' if len(synced_users) > 10 else ''}")
        
        # Summary log
        logger.info(f"[TRACE][SCHEDULE_SYNC] ========== SYNC SUMMARY ==========")
        logger.info(f"[TRACE][SCHEDULE_SYNC] Identifier column: '{identifier_column}'")
        logger.info(f"[TRACE][SCHEDULE_SYNC] Total rows processed: {total_rows}")
        logger.info(f"[TRACE][SCHEDULE_SYNC] Schedule entries stored: {rows_synced}")
        logger.info(f"[TRACE][SCHEDULE_SYNC] Users synced: {users_synced}")
        logger.info(f"[TRACE][SCHEDULE_SYNC] ==================================")
        
        return rows_synced, users_synced
    
    def _parse_date(self, date_str: str) -> Optional[datetime.date]:
        """Parse date from various formats"""
        if not date_str:
            return None
        
        date_str = str(date_str).strip()
        
        # Try common date formats
        formats = [
            '%Y-%m-%d',      # 2025-11-03
            '%Y/%m/%d',      # 2025/11/03
            '%m/%d/%Y',      # 11/03/2025
            '%Y年%m月%d日',  # 2025年11月03日
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt).date()
                return parsed
            except:
                continue
        
        # Try to extract date from string using regex
        import re
        # Match patterns like "2025/10/01" or "2025-10-01"
        match = re.search(r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})', date_str)
        if match:
            year, month, day = map(int, match.groups())
            try:
                parsed = datetime(year, month, day).date()
                return parsed
            except ValueError:
                pass
        
        # Try to parse as ISO format
        try:
            parsed = datetime.fromisoformat(date_str.replace('/', '-')).date()
            return parsed
        except:
            pass
        
        return None
    
    def _normalize_shift_type(self, shift_value: str) -> str:
        """Normalize shift type from various formats"""
        if not shift_value:
            return 'OFF'
        
        shift_upper = str(shift_value).upper().strip()
        
        # Check for OFF first
        if shift_upper in ['OFF', '休', '休假', 'NULL', ''] or shift_upper == '':
            return 'OFF'
        
        # Check if it's a complex shift description (e.g., "A 櫃台人力", "B 二線人力")
        # These should be treated as work shifts (D)
        if any(keyword in shift_upper for keyword in ['櫃台', '二線', '藥局', '人力', 'COUNTER', 'DESK', 'PHARMACY']):
            return 'D'  # Treat complex shift descriptions as day shift
        
        # Check for simple shift codes
        if shift_upper in ['E', 'EVENING', '小夜']:
            return 'E'
        elif shift_upper in ['N', 'NIGHT', '大夜']:
            return 'N'
        elif shift_upper in ['D', 'DAY', '白班']:
            return 'D'
        else:
            # Default to D if single letter
            if len(shift_upper) == 1 and shift_upper in ['D', 'E', 'N']:
                return shift_upper
            # For unknown complex values, default to D (work shift)
            return 'D'
    
    def _get_time_range(self, shift_type: str) -> str:
        """Get default time range for shift type"""
        time_ranges = {
            'D': '08:00 - 16:00',
            'E': '16:00 - 00:00',
            'N': '00:00 - 08:00',
            'OFF': '--'
        }
        return time_ranges.get(shift_type, '--')
    
    def sync_schedule_definition_metadata(self, schedule_def: 'ScheduleDefinition', 
                                         credentials_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Sync metadata from Google Sheets for a schedule definition
        
        Fetches live data from Google Sheets (paramsSheetURL) and updates the schedule definition's
        metadata with row count, preview data, and last sync timestamp.
        
        Args:
            schedule_def: ScheduleDefinition instance to sync
            credentials_path: Path to Google service account credentials
            
        Returns:
            Dictionary with sync results
        """
        if not schedule_def or not schedule_def.paramsSheetURL:
            return {
                'success': False,
                'error': 'Schedule definition or paramsSheetURL is missing'
            }
        
        try:
            # Import Google Sheets service using the shared import utility
            # This handles multiple import paths and fallbacks
            try:
                from app.services.google_sheets_import import GoogleSheetsService, SHEETS_AVAILABLE
                
                # Ensure import was attempted
                from app.services.google_sheets_import import _try_import_google_sheets
                _try_import_google_sheets(force_retry=False)
                
                if not SHEETS_AVAILABLE or not GoogleSheetsService:
                    logger.warning("[Google Sheets Sync Error] Google Sheets service not available after import")
                    return {
                        'success': False,
                        'error': 'Google Sheets service not available',
                        'skipped': True
                    }
            except ImportError as e:
                logger.warning(f"[Google Sheets Sync Error] Failed to import GoogleSheetsService: {str(e)}")
                return {
                    'success': False,
                    'error': 'Google Sheets service not available',
                    'skipped': True
                }
            
            # Get credentials path
            if not credentials_path:
                from flask import current_app
                credentials_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
            
            # Initialize Google Sheets service
            service = GoogleSheetsService(credentials_path)
            
            # Fetch data from paramsSheetURL
            logger.info(f"[Google Sheets Sync] Fetching metadata from {schedule_def.paramsSheetURL}")
            params_result = service.read_parameters_sheet(schedule_def.paramsSheetURL)
            
            if not params_result.get('success'):
                error_msg = params_result.get('error', 'Unknown error')
                logger.warning(f"[Google Sheets Sync Error] Failed to fetch params sheet: {error_msg}")
                # Don't fail - just log and return DB data
                return {
                    'success': False,
                    'error': error_msg,
                    'skipped': True
                }
            
            # Extract metadata
            row_count = params_result.get('rows', 0)
            columns = params_result.get('columns', [])
            data = params_result.get('data', [])
            
            # Get preview rows (first 5 rows)
            preview_rows = data[:5] if data else []
            
            # Try to read preschedule sheet for additional info
            preschedule_result = None
            if schedule_def.prefsSheetURL:
                try:
                    preschedule_result = service.read_preschedule_sheet(schedule_def.prefsSheetURL)
                    if preschedule_result.get('success'):
                        logger.info(f"[Google Sheets Sync] Preschedule sheet has {preschedule_result.get('rows', 0)} rows")
                except Exception as e:
                    logger.warning(f"[Google Sheets Sync Error] Could not read preschedule sheet: {str(e)}")
            
            # Build metadata dictionary
            metadata = {
                'last_synced_at': datetime.utcnow().isoformat(),
                'params_sheet': {
                    'row_count': row_count,
                    'column_count': len(columns),
                    'columns': columns[:10],  # First 10 columns
                    'preview_rows': preview_rows,
                    'sheet_name': params_result.get('sheet_name', ''),
                },
                'preschedule_sheet': None,
            }
            
            if preschedule_result and preschedule_result.get('success'):
                metadata['preschedule_sheet'] = {
                    'row_count': preschedule_result.get('rows', 0),
                    'column_count': len(preschedule_result.get('columns', [])),
                    'sheet_name': preschedule_result.get('sheet_name', ''),
                }
            
            # Update schedule definition metadata
            # Check if model has metadata field, otherwise store in remarks or use JSON serialization
            try:
                # Try to set metadata field if it exists
                if hasattr(schedule_def, 'metadata'):
                    import json
                    if isinstance(schedule_def.metadata, dict):
                        schedule_def.metadata.update(metadata)
                    else:
                        schedule_def.metadata = metadata
                else:
                    # Store in a JSON field or use JSON serialization in remarks
                    # For now, we'll store a summary in remarks if metadata field doesn't exist
                    # This ensures backward compatibility
                    import json
                    metadata_json = json.dumps(metadata, ensure_ascii=False)
                    # Store in remarks with a prefix (we'll append, not replace)
                    if not schedule_def.remarks or '[SYNC]' not in schedule_def.remarks:
                        sync_info = f"\n[SYNC] Last synced: {metadata['last_synced_at']}, Rows: {row_count}"
                        schedule_def.remarks = (schedule_def.remarks or '') + sync_info
            except Exception as e:
                logger.warning(f"[Google Sheets Sync Error] Could not update metadata: {str(e)}")
                # Continue anyway - metadata update is not critical
            
            # Update updated_at timestamp
            schedule_def.updated_at = db.func.now()
            
            # Commit changes
            db.session.commit()
            
            logger.info(f"[Google Sheets Sync] Successfully synced metadata for {schedule_def.scheduleName}: {row_count} rows")
            
            return {
                'success': True,
                'row_count': row_count,
                'column_count': len(columns),
                'last_synced_at': metadata['last_synced_at'],
                'metadata': metadata
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Google Sheets Sync Error] Sync failed for {schedule_def.scheduleDefID}: {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Don't fail the request - return error but continue with DB data
            return {
                'success': False,
                'error': error_msg,
                'skipped': True
            }