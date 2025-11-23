"""
Schedule task model for tracking scheduling jobs
"""

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..extensions import db
from ..database.connection import Base as AlembicBase  # For Alembic compatibility


class ScheduleTask(db.Model):
    """Schedule task model"""
    __tablename__ = "schedule_tasks"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.userID'), nullable=False)
    task_id = db.Column(db.String(255), unique=True, index=True, nullable=False)  # Celery task ID
    
    # Task configuration
    input_source = db.Column(db.String(50), nullable=False)  # 'excel' or 'google_sheets'
    input_config = db.Column(db.JSON, nullable=False)  # Input configuration
    output_destination = db.Column(db.String(50), nullable=False)  # 'excel' or 'google_sheets'
    output_config = db.Column(db.JSON, nullable=False)  # Output configuration
    
    # Task parameters
    time_limit = db.Column(db.Integer, default=90)  # Time limit in seconds
    debug_shift = db.Column(db.String(255), nullable=True)
    log_level = db.Column(db.String(20), default="INFO")
    
    # Task status
    status = db.Column(db.String(50), default="pending")  # pending, running, success, failed, cancelled
    progress = db.Column(db.Integer, default=0)  # Progress percentage (0-100)
    
    # Results
    result_data = db.Column(db.JSON, nullable=True)  # Task result data
    error_message = db.Column(db.Text, nullable=True)  # Error message if failed
    
    # File storage
    input_file_path = db.Column(db.String(500), nullable=True)  # Path to uploaded input file
    output_file_path = db.Column(db.String(500), nullable=True)  # Path to generated output file
    chart_file_path = db.Column(db.String(500), nullable=True)  # Path to generated chart
    
    # Google Sheets URLs
    input_sheet_url = db.Column(db.String(500), nullable=True)
    output_sheet_url = db.Column(db.String(500), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    # Note: User model doesn't have schedule_tasks relationship, so this is commented out
    # user = relationship("User", back_populates="schedule_tasks")
    
    def __repr__(self):
        return f"<ScheduleTask(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"


# Note: This model uses Flask-SQLAlchemy (db.Model) for runtime
# Alembic will use db.metadata from Flask-SQLAlchemy, not AlembicBase
