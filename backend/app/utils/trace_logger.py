"""
Centralized Trace Logging System
Logs every stage of data flow from import to API to frontend
"""
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime

# Create trace logger
trace_logger = logging.getLogger('trace')
trace_logger.setLevel(logging.INFO)

# Create handler if not exists
if not trace_logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[TRACE] %(message)s')
    handler.setFormatter(formatter)
    trace_logger.addHandler(handler)


def trace_log(stage: str, filename: str, detail: str, extra: Optional[Dict[str, Any]] = None):
    """
    Log a trace event
    
    Args:
        stage: Stage name (Import, API Request, Sheets Fetch, Response, etc.)
        filename: File or module name
        detail: Specific information about this stage
        extra: Optional additional context
    """
    # Build log message without using reserved LogRecord fields in extra
    log_message = f"Stage={stage} | File={filename} | Detail={detail}"
    if extra:
        extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
        log_message += f" | {extra_str}"
    trace_logger.info(log_message)


def trace_import_success(module_name: str, import_path: str):
    """Log successful import"""
    trace_log(
        stage='ImportSuccess',
        filename='service_loader.py',
        detail=f'Google Sheets loaded from {import_path}',
        extra={'module': module_name, 'path': import_path}
    )


def trace_import_failure(reason: str, attempts: int = 0):
    """Log import failure"""
    trace_log(
        stage='ImportFailFinal',
        filename='service_loader.py',
        detail=f'No valid module found: {reason}',
        extra={'attempts': attempts}
    )


def trace_api_request(endpoint: str, user_id: Optional[str] = None, params: Optional[Dict] = None):
    """Log API request"""
    detail = f'Endpoint={endpoint}'
    if user_id:
        detail += f' | User={user_id}'
    if params:
        detail += f' | Params={params}'
    
    trace_log(
        stage='API Request',
        filename='routes',
        detail=detail
    )


def trace_sheets_fetch(rows: Optional[int] = None, month: Optional[str] = None, success: bool = True):
    """Log sheets fetch"""
    detail_parts = []
    if rows is not None:
        detail_parts.append(f'Rows={rows}')
    if month:
        detail_parts.append(f'Month={month}')
    detail_parts.append(f'Success={success}')
    
    trace_log(
        stage='Sheets Fetch',
        filename='sheets_service.py',
        detail=' | '.join(detail_parts)
    )


def trace_response(status: int, duration_ms: Optional[float] = None, endpoint: Optional[str] = None):
    """Log API response"""
    detail_parts = [f'Status={status}']
    if duration_ms is not None:
        detail_parts.append(f'Duration={duration_ms:.0f}ms')
    if endpoint:
        detail_parts.append(f'Endpoint={endpoint}')
    
    trace_log(
        stage='Response',
        filename='routes',
        detail=' | '.join(detail_parts)
    )


def trace_startup(detail: str):
    """Log startup event"""
    trace_log(
        stage='Startup',
        filename='main.py',
        detail=detail
    )


def trace_error(stage: str, filename: str, error: str):
    """Log error"""
    trace_log(
        stage=f'{stage}Error',
        filename=filename,
        detail=f'Error: {error}'
    )

