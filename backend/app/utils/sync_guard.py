"""
Sync Guard Utility
Lightweight utility to ensure data is synced from Google Sheets before API responses.

This module provides a simple function to check if cached data exists and is fresh,
and automatically triggers a sync if needed.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from flask import current_app

from ..models import CachedSchedule, SyncLog, ScheduleDefinition, User, EmployeeMapping
from ..services.google_sheets_sync_service import GoogleSheetsSyncService

logger = logging.getLogger(__name__)


def ensure_data_synced(
    user_id: str,
    schedule_def_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    max_age_minutes: int = 30,
    force_check: bool = False
) -> Dict[str, Any]:
    """
    Ensure schedule data is synced for a user.
    
    Checks if cached data exists and is fresh. If not, triggers a sync from Google Sheets.
    This is a lightweight, synchronous check that can be called from API endpoints.
    
    Args:
        user_id: User ID to check sync for
        schedule_def_id: Optional schedule definition ID (if None, uses active schedule for user's tenant)
        employee_id: Optional employee_id for logging (if None, fetches from user)
        max_age_minutes: Maximum age of cached data in minutes (default 30)
        force_check: If True, always check even if recent sync exists
        
    Returns:
        Dictionary with sync status:
        {
            'synced': bool,  # Whether sync was triggered
            'used_cache': bool,  # Whether cached data was used
            'last_synced_at': str or None,  # ISO timestamp of last sync
            'sync_result': dict or None  # Result from sync if triggered
        }
    """
    try:
        # Get user
        user = User.query.get(user_id)
        if not user:
            logger.warning(f"[TRACE][SYNC] User {user_id} not found")
            return {
                'synced': False,
                'used_cache': False,
                'last_synced_at': None,
                'sync_result': None,
                'error': 'User not found'
            }
        
        # Get employee_id if not provided
        # For employees, username IS the employee_id, so use username if employee_id is not set
        if not employee_id:
            employee_id = user.employee_id
            # For employee role, if employee_id is not set, use username (which is the employee_id)
            if not employee_id and user.role and user.role.lower() == 'employee' and user.username:
                employee_id = user.username
                logger.info(f"[TRACE][SYNC] Using username as employee_id for employee user: {user.username}")
        
        # Get schedule definition
        if not schedule_def_id:
            schedule_def = ScheduleDefinition.query.filter_by(
                tenantID=user.tenantID,
                is_active=True
            ).first()
            if not schedule_def:
                logger.debug(f"[TRACE][SYNC] No active schedule definition for tenant {user.tenantID}")
                return {
                    'synced': False,
                    'used_cache': False,
                    'last_synced_at': None,
                    'sync_result': None,
                    'error': 'No active schedule definition'
                }
            schedule_def_id = schedule_def.scheduleDefID
        else:
            schedule_def = ScheduleDefinition.query.get(schedule_def_id)
            if not schedule_def:
                logger.warning(f"[TRACE][SYNC] Schedule definition {schedule_def_id} not found")
                return {
                    'synced': False,
                    'used_cache': False,
                    'last_synced_at': None,
                    'sync_result': None,
                    'error': 'Schedule definition not found'
                }
        
        # Check if user has cached schedule data
        cached_schedule = CachedSchedule.query.filter_by(
            user_id=user_id,
            schedule_def_id=schedule_def_id
        ).order_by(CachedSchedule.updated_at.desc()).first()
        
        # Check last sync time
        last_sync = SyncLog.get_last_sync(schedule_def_id=schedule_def_id)
        last_synced_at = last_sync.completed_at if last_sync and last_sync.completed_at else None
        
        # Determine if sync is needed
        needs_sync = False
        sync_reason = None
        
        if not cached_schedule:
            needs_sync = True
            sync_reason = "no cached data"
            logger.info(f"[TRACE][SYNC] Auto-sync triggered for employee_id={employee_id}: {sync_reason}")
        elif force_check:
            needs_sync = True
            sync_reason = "force check requested"
            logger.info(f"[TRACE][SYNC] Auto-sync triggered for employee_id={employee_id}: {sync_reason}")
        elif not last_synced_at:
            needs_sync = True
            sync_reason = "no previous sync"
            logger.info(f"[TRACE][SYNC] Auto-sync triggered for employee_id={employee_id}: {sync_reason}")
        else:
            # Check if data is stale
            age_minutes = (datetime.utcnow() - last_synced_at).total_seconds() / 60
            if age_minutes > max_age_minutes:
                needs_sync = True
                sync_reason = f"data is {age_minutes:.1f} minutes old (threshold: {max_age_minutes} minutes)"
                logger.info(f"[TRACE][SYNC] Auto-sync triggered for employee_id={employee_id}: {sync_reason}")
            else:
                # Data is fresh, use cache
                logger.debug(f"[TRACE][SYNC] Using cached data from DB (last updated: {last_synced_at.isoformat()})")
                return {
                    'synced': False,
                    'used_cache': True,
                    'last_synced_at': last_synced_at.isoformat(),
                    'sync_result': None,
                    'reason': f'Data is fresh ({age_minutes:.1f} minutes old)'
                }
        
        # Sync is needed - trigger it
        if needs_sync:
            logger.info(f"[TRACE][SYNC] Fetching schedule data from Google Sheets for employee_id={employee_id}...")
            
            try:
                # Get credentials path
                creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
                
                # Create sync service and trigger sync
                sync_service = GoogleSheetsSyncService(creds_path)
                sync_result = sync_service.sync_schedule_data(
                    schedule_def_id=schedule_def_id,
                    sync_type='auto',
                    triggered_by=user_id,
                    force=False  # Don't force - respect rate limits
                )
                
                if sync_result.get('success'):
                    rows_synced = sync_result.get('rows_synced', 0)
                    users_synced = sync_result.get('users_synced', 0)
                    logger.info(f"[TRACE][SYNC] {rows_synced} records fetched and saved to DB (users: {users_synced})")
                    logger.info(f"[TRACE][SYNC] Auto-sync completed successfully for employee_id={employee_id}")
                    
                    # Get updated last sync time
                    updated_last_sync = SyncLog.get_last_sync(schedule_def_id=schedule_def_id)
                    updated_last_synced_at = updated_last_sync.completed_at.isoformat() if updated_last_sync and updated_last_sync.completed_at else None
                    
                    return {
                        'synced': True,
                        'used_cache': False,
                        'last_synced_at': updated_last_synced_at,
                        'sync_result': sync_result,
                        'reason': sync_reason
                    }
                else:
                    # Sync failed but might have partial data
                    error_msg = sync_result.get('error', 'Unknown error')
                    logger.warning(f"[TRACE][SYNC][ERROR] Auto-sync failed for employee_id={employee_id}: {error_msg}")
                    
                    # Still return cached data if available
                    if cached_schedule and last_synced_at:
                        logger.info(f"[TRACE][SYNC] Using cached data despite sync failure (last updated: {last_synced_at.isoformat()})")
                        return {
                            'synced': False,
                            'used_cache': True,
                            'last_synced_at': last_synced_at.isoformat(),
                            'sync_result': sync_result,
                            'error': error_msg,
                            'reason': 'Sync failed, using cached data'
                        }
                    else:
                        return {
                            'synced': False,
                            'used_cache': False,
                            'last_synced_at': last_synced_at.isoformat() if last_synced_at else None,
                            'sync_result': sync_result,
                            'error': error_msg,
                            'reason': 'Sync failed, no cached data available'
                        }
                        
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[TRACE][SYNC][ERROR] Exception during auto-sync for employee_id={employee_id}: {error_msg}")
                import traceback
                logger.error(traceback.format_exc())
                
                # Return cached data if available
                if cached_schedule and last_synced_at:
                    logger.info(f"[TRACE][SYNC] Using cached data despite exception (last updated: {last_synced_at.isoformat()})")
                    return {
                        'synced': False,
                        'used_cache': True,
                        'last_synced_at': last_synced_at.isoformat(),
                        'sync_result': None,
                        'error': error_msg,
                        'reason': 'Exception during sync, using cached data'
                    }
                else:
                    return {
                        'synced': False,
                        'used_cache': False,
                        'last_synced_at': last_synced_at.isoformat() if last_synced_at else None,
                        'sync_result': None,
                        'error': error_msg,
                        'reason': 'Exception during sync, no cached data available'
                    }
        
        # Should not reach here, but return safe default
        return {
            'synced': False,
            'used_cache': True,
            'last_synced_at': last_synced_at.isoformat() if last_synced_at else None,
            'sync_result': None
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[TRACE][SYNC][ERROR] Unexpected error in ensure_data_synced: {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'synced': False,
            'used_cache': False,
            'last_synced_at': None,
            'sync_result': None,
            'error': error_msg
        }

