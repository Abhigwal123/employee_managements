"""
Schedule task schemas for API requests and responses
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ScheduleTaskBase(BaseModel):
    """Base schedule task schema"""
    input_source: str = Field(..., description="Input source type: 'excel' or 'google_sheets'")
    input_config: Dict[str, Any] = Field(..., description="Input configuration")
    output_destination: str = Field(..., description="Output destination type: 'excel' or 'google_sheets'")
    output_config: Dict[str, Any] = Field(..., description="Output configuration")
    time_limit: int = Field(90, ge=30, le=600, description="Time limit in seconds")
    debug_shift: Optional[str] = Field(None, description="Debug shift in format 'YYYY/MM/DD,班別,崗位'")
    log_level: str = Field("INFO", description="Logging level")


class ScheduleTaskCreate(ScheduleTaskBase):
    """Schedule task creation schema"""
    pass


class ScheduleTaskUpdate(BaseModel):
    """Schedule task update schema"""
    status: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    output_file_path: Optional[str] = None
    chart_file_path: Optional[str] = None
    output_sheet_url: Optional[str] = None


class ScheduleTaskInDB(ScheduleTaskBase):
    """Schedule task in database schema"""
    id: int
    user_id: int
    task_id: str
    status: str
    progress: int
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    input_file_path: Optional[str] = None
    output_file_path: Optional[str] = None
    chart_file_path: Optional[str] = None
    input_sheet_url: Optional[str] = None
    output_sheet_url: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ScheduleTask(ScheduleTaskBase):
    """Schedule task response schema"""
    id: int
    task_id: str
    status: str
    progress: int
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    output_file_path: Optional[str] = None
    chart_file_path: Optional[str] = None
    output_sheet_url: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ScheduleTaskResponse(BaseModel):
    """Schedule task creation response"""
    task_id: str
    message: str
    status: str = "pending"


class TaskStatus(BaseModel):
    """Task status response"""
    task_id: str
    status: str
    progress: int
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
