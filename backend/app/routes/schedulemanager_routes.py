from flask import Blueprint, jsonify, request
from celery.result import AsyncResult
from celery import current_app as celery_current_app
from ..utils.auth import role_required
from flask import current_app
from ..services.google_io import summarize_sheet_target, get_default_input_url, get_default_output_url


# Note: url_prefix set to None - will be set during registration in __init__.py
schedulemanager_bp = Blueprint("schedulemanager", __name__)


@schedulemanager_bp.route("/dashboard", methods=["GET"])
@role_required("ScheduleManager")
def dashboard():
    """Schedule Manager dashboard with scheduling, run, and export views"""
    from flask_jwt_extended import get_jwt_identity
    from app.models import User, ScheduleDefinition, ScheduleJobLog
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            response = jsonify({"success": False, "error": "User not found"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404
        
        # Get user's accessible schedule definitions
        from app.models import SchedulePermission
        permissions = SchedulePermission.get_valid_by_user(user.userID)
        schedule_def_ids = [p.scheduleDefID for p in permissions]
        
        # Get recent job logs for user's schedules
        recent_jobs = ScheduleJobLog.query.filter(
            ScheduleJobLog.tenantID == user.tenantID,
            ScheduleJobLog.scheduleDefID.in_(schedule_def_ids) if schedule_def_ids else False
        ).order_by(ScheduleJobLog.startTime.desc()).limit(10).all() if schedule_def_ids else []
        
        logger.info(f"[TRACE] ScheduleManager dashboard - accessible_schedules: {len(schedule_def_ids)}, recent_jobs: {len(recent_jobs)}")
        
        response = jsonify({
            "success": True,
            "dashboard": "schedulemanager",
            "user": user.to_dict(),
            "accessible_schedules": len(schedule_def_ids),
            "recent_jobs": [job.to_dict() for job in recent_jobs],
            "views": ["D1: Scheduling", "D2: Run", "D3: Export"]
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
    except Exception as e:
        logger.error(f"Error in schedulemanager dashboard: {e}")
        import traceback
        logger.error(traceback.format_exc())
        response = jsonify({"success": False, "error": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


@schedulemanager_bp.route("/run-task", methods=["POST"])
@role_required("ScheduleManager")
def run_task():
    """Run a scheduling task - redirects to schedule-job-logs/run endpoint"""
    from flask import redirect
    
    # Use the proper endpoint from schedule_job_log_routes
    body = request.get_json(silent=True) or {}
    schedule_def_id = body.get("scheduleDefID")
    
    if not schedule_def_id:
        return jsonify({"error": "scheduleDefID is required"}), 400
    
    # Forward to the schedule job logs run endpoint
    return redirect(f"/api/v1/schedule-job-logs/run", code=307)


@schedulemanager_bp.route("/task-status/<task_id>", methods=["GET"])
@role_required("ScheduleManager")
def task_status(task_id: str):
    result = AsyncResult(task_id)
    payload = {"state": result.state}
    if result.state == "SUCCESS":
        payload["result"] = result.result
    elif result.state == "FAILURE":
        payload["error"] = str(result.info)
    return jsonify(payload)


@schedulemanager_bp.route("/logs", methods=["GET"])
@role_required("ScheduleManager")
def logs():
    """Get schedule job logs for current user"""
    import logging
    trace_logger = logging.getLogger('trace')
    
    trace_logger.info("[TRACE] Backend: GET /schedulemanager/logs")
    trace_logger.info(f"[TRACE] Backend: Query params: {dict(request.args)}")
    
    from flask_jwt_extended import get_jwt_identity, get_jwt
    from app.models import User, ScheduleJobLog
    from datetime import datetime, timedelta
    
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt() or {}
        trace_logger.info(f"[TRACE] Backend: User ID: {current_user_id}")
        trace_logger.info(f"[TRACE] Backend: Role: {claims.get('role')}")
        
        user = User.query.get(current_user_id)
        
        if not user:
            response = jsonify({"error": "User not found"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        hours = request.args.get('hours', 24, type=int)
        
        trace_logger.info(f"[DEBUG] Fetch Params → limit={limit}, hours={hours}")
        
        # Get recent job logs for user's tenant
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        job_logs = ScheduleJobLog.query.filter(
            ScheduleJobLog.tenantID == user.tenantID,
            ScheduleJobLog.startTime >= cutoff_time
        ).order_by(ScheduleJobLog.startTime.desc()).limit(limit).all()
        
        trace_logger.info(f"[DEBUG] Checking Schedule Logs → count: {len(job_logs)}")
        if len(job_logs) == 0:
            trace_logger.warning(f"[DEBUG] No logs found - tenantID: {user.tenantID}, cutoff_time: {cutoff_time}")
        
        response = jsonify({
            "success": True,
            "logs": [log.to_dict() for log in job_logs],
            "data": [log.to_dict() for log in job_logs],  # Frontend compatibility
            "count": len(job_logs)
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200
    except Exception as e:
        trace_logger.error(f"[TRACE] Backend: Error in /schedulemanager/logs: {e}")
        import traceback
        trace_logger.error(traceback.format_exc())
        response = jsonify({"error": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


@schedulemanager_bp.route("/results/<sheet_id>", methods=["GET"])
@role_required("ScheduleManager")
def results(sheet_id: str):
    return jsonify(summarize_sheet_target(sheet_id))


@schedulemanager_bp.route("/d1-scheduling", methods=["GET"])
@role_required("ScheduleManager")
def d1_scheduling():
    """D1 Scheduling Dashboard - View scheduling data from Google Sheets"""
    from flask_jwt_extended import get_jwt_identity
    from app.services.dashboard_data_service import DashboardDataService
    
    try:
        current_user_id = get_jwt_identity()
        schedule_def_id = request.args.get('schedule_def_id')
        
        creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
        service = DashboardDataService(creds_path)
        dashboard_data = service.get_schedule_manager_d1_data(current_user_id, schedule_def_id)
        
        if dashboard_data.get("success"):
            return jsonify(dashboard_data), 200
        else:
            return jsonify(dashboard_data), 400
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in D1 dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@schedulemanager_bp.route("/d2-run", methods=["GET"])
@role_required("ScheduleManager")
def d2_run():
    """D2 Run Dashboard - Data needed to run schedule from Google Sheets"""
    from flask_jwt_extended import get_jwt_identity
    from app.services.dashboard_data_service import DashboardDataService
    
    try:
        current_user_id = get_jwt_identity()
        schedule_def_id = request.args.get('schedule_def_id')
        
        creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
        service = DashboardDataService(creds_path)
        dashboard_data = service.get_schedule_manager_d2_data(current_user_id, schedule_def_id)
        
        if dashboard_data.get("success"):
            return jsonify(dashboard_data), 200
        else:
            return jsonify(dashboard_data), 400
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in D2 dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@schedulemanager_bp.route("/d3-export", methods=["GET"])
@role_required("ScheduleManager")
def d3_export():
    """D3 Export Dashboard - Final output from Google Sheets for export"""
    from flask_jwt_extended import get_jwt_identity
    from app.services.dashboard_data_service import DashboardDataService
    
    try:
        current_user_id = get_jwt_identity()
        schedule_def_id = request.args.get('schedule_def_id')
        
        creds_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-creds.json')
        service = DashboardDataService(creds_path)
        dashboard_data = service.get_schedule_manager_d3_data(current_user_id, schedule_def_id)
        
        if dashboard_data.get("success"):
            return jsonify(dashboard_data), 200
        else:
            return jsonify(dashboard_data), 400
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in D3 dashboard: {e}")
        return jsonify({"error": str(e)}), 500


