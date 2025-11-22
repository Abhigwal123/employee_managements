# Marshmallow Schemas for Validation and Serialization
from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from datetime import datetime
from typing import Dict, Any
import re

class BaseSchema(Schema):
    """Base schema with common fields and validation methods"""
    class Meta:
        ordered = True
    
    def handle_error(self, error, data, **kwargs):
        """Custom error handler for better error messages"""
        if isinstance(error, ValidationError):
            return error.messages
        return {'_schema': ['Unknown validation error']}

class TenantSchema(BaseSchema):
    """Schema for Tenant model validation and serialization"""
    
    id = fields.Int(dump_only=True)
    tenantID = fields.Str(required=False, allow_none=True)
    tenantName = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    code = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    
    @validates_schema
    def validate_tenant_name(self, data, **kwargs):
        """Validate tenant name"""
        if 'tenantName' in data:
            name = data['tenantName'].strip()
            if not name:
                raise ValidationError('Tenant name cannot be empty', 'tenantName')
            data['tenantName'] = name

class TenantUpdateSchema(BaseSchema):
    """Schema for updating Tenant model"""
    
    tenantName = fields.Str(validate=validate.Length(min=1, max=255))
    is_active = fields.Bool()

class UserSchema(BaseSchema):
    """Schema for User model validation and serialization"""
    
    userID = fields.Str(required=False, allow_none=True)
    tenantID = fields.Str(required=False, allow_none=True)
    username = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    password = fields.Str(required=True, validate=validate.Length(min=8))
    role = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    status = fields.Str(required=False, validate=validate.OneOf(['active', 'inactive', 'suspended']))
    email = fields.Email(allow_none=True)
    full_name = fields.Str(validate=validate.Length(max=255), allow_none=True)
    
    @validates_schema
    def validate_username(self, data, **kwargs):
        """Validate username format"""
        if 'username' in data and data['username'] is not None:
            username = data['username'].strip()
            if not re.match(r'^[a-zA-Z0-9_.@-]+$', username):
                raise ValidationError('Username can only contain letters, numbers, dots, hyphens, underscores, and @', 'username')
            data['username'] = username
    
    @validates_schema
    def validate_password(self, data, **kwargs):
        """Validate password strength"""
        if 'password' in data:
            password = data['password']
            if not re.search(r'[A-Z]', password):
                raise ValidationError('Password must contain at least one uppercase letter', 'password')
            if not re.search(r'[a-z]', password):
                raise ValidationError('Password must contain at least one lowercase letter', 'password')
            if not re.search(r'\d', password):
                raise ValidationError('Password must contain at least one digit', 'password')

class UserUpdateSchema(BaseSchema):
    """Schema for updating User model"""
    
    username = fields.Str(validate=validate.Length(min=3, max=100), allow_none=True)
    password = fields.Str(validate=validate.Length(min=6), allow_none=True)  # Optional password update
    role = fields.Str(allow_none=True)  # Allow any role (validation done in route)
    status = fields.Str(validate=validate.OneOf(['active', 'inactive', 'suspended']), allow_none=True)
    email = fields.Email(allow_none=True)
    full_name = fields.Str(validate=validate.Length(max=255), allow_none=True)
    employee_id = fields.Str(allow_none=True)
    departmentID = fields.Str(allow_none=True)

class UserLoginSchema(BaseSchema):
    """Schema for user login"""
    
    username = fields.Str(required=True, validate=validate.Length(min=1))
    password = fields.Str(required=True, validate=validate.Length(min=1))

class DepartmentSchema(BaseSchema):
    """Schema for Department model validation and serialization"""
    
    departmentID = fields.Str(required=False, allow_none=True)
    tenantID = fields.Str(required=False, allow_none=True)  # Auto-set from current user
    departmentName = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)
    # Allow managerID/manager_id fields but ignore them (not in model, just for frontend display)
    managerID = fields.Str(required=False, allow_none=True)
    manager_id = fields.Str(required=False, allow_none=True)
    
    @validates_schema
    def validate_department_name(self, data, **kwargs):
        """Validate department name"""
        if 'departmentName' in data:
            name = data['departmentName'].strip()
            if not name:
                raise ValidationError('Department name cannot be empty', 'departmentName')
            data['departmentName'] = name

class DepartmentUpdateSchema(BaseSchema):
    """Schema for updating Department model"""
    
    departmentName = fields.Str(validate=validate.Length(min=1, max=255), allow_none=True)
    description = fields.Str(allow_none=True)
    is_active = fields.Bool(allow_none=True)
    # Allow managerID/manager_id fields but ignore them (not in model, just for frontend display)
    managerID = fields.Str(required=False, allow_none=True)
    manager_id = fields.Str(required=False, allow_none=True)

class ScheduleDefinitionSchema(BaseSchema):
    """Schema for ScheduleDefinition model validation and serialization"""
    
    scheduleDefID = fields.Str(required=False, allow_none=True)
    tenantID = fields.Str(required=True)
    departmentID = fields.Str(required=True)
    scheduleName = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    paramsSheetURL = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    prefsSheetURL = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    resultsSheetURL = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    schedulingAPI = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    remarks = fields.Str(allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)
    
    @validates_schema
    def validate_urls(self, data, **kwargs):
        """Validate URL formats"""
        url_fields = ['paramsSheetURL', 'prefsSheetURL', 'resultsSheetURL', 'schedulingAPI']
        
        for field in url_fields:
            if field in data:
                url = data[field]
                if not re.match(r'^https?://', url):
                    raise ValidationError(f'{field} must be a valid HTTP/HTTPS URL', field)
    
    @validates_schema
    def validate_schedule_name(self, data, **kwargs):
        """Validate schedule name"""
        if 'scheduleName' in data:
            name = data['scheduleName'].strip()
            if not name:
                raise ValidationError('Schedule name cannot be empty', 'scheduleName')
            data['scheduleName'] = name

class ScheduleDefinitionUpdateSchema(BaseSchema):
    """Schema for updating ScheduleDefinition model"""
    
    scheduleName = fields.Str(validate=validate.Length(min=1, max=255))
    paramsSheetURL = fields.Str(validate=validate.Length(min=1, max=500))
    prefsSheetURL = fields.Str(validate=validate.Length(min=1, max=500))
    resultsSheetURL = fields.Str(validate=validate.Length(min=1, max=500))
    schedulingAPI = fields.Str(validate=validate.Length(min=1, max=500))
    remarks = fields.Str(allow_none=True)
    is_active = fields.Bool()

class SchedulePermissionSchema(BaseSchema):
    """Schema for SchedulePermission model validation and serialization"""
    
    permissionID = fields.Str(required=False, allow_none=True)
    tenantID = fields.Str(required=True)
    userID = fields.Str(required=True)
    scheduleDefID = fields.Str(required=True)
    canRunJob = fields.Bool(required=True)
    granted_by = fields.Str(allow_none=True)
    expires_at = fields.DateTime(allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class SchedulePermissionUpdateSchema(BaseSchema):
    """Schema for updating SchedulePermission model"""
    
    canRunJob = fields.Bool()
    expires_at = fields.DateTime(allow_none=True)
    is_active = fields.Bool()

class ScheduleJobLogSchema(BaseSchema):
    """Schema for ScheduleJobLog model validation and serialization"""
    
    logID = fields.Str(required=False, allow_none=True)
    tenantID = fields.Str(required=True)
    scheduleDefID = fields.Str(required=True)
    runByUserID = fields.Str(required=True)
    startTime = fields.DateTime(required=False, allow_none=True)
    endTime = fields.DateTime(allow_none=True)
    status = fields.Str(required=False, validate=validate.OneOf(['pending', 'running', 'success', 'failed', 'cancelled']))
    resultSummary = fields.Str(allow_none=True)
    error_message = fields.Str(allow_none=True)
    metadata = fields.Dict(allow_none=True)

class ScheduleJobLogUpdateSchema(BaseSchema):
    """Schema for updating ScheduleJobLog model"""
    
    endTime = fields.DateTime(allow_none=True)
    status = fields.Str(validate=validate.OneOf(['pending', 'running', 'success', 'failed', 'cancelled']))
    resultSummary = fields.Str(allow_none=True)
    error_message = fields.Str(allow_none=True)
    metadata = fields.Dict(allow_none=True)

class JobRunSchema(BaseSchema):
    """Schema for running a schedule job"""
    
    scheduleDefID = fields.Str(required=True)
    parameters = fields.Dict(allow_none=True)
    priority = fields.Str(required=False, validate=validate.OneOf(['low', 'normal', 'high']))

class PaginationSchema(BaseSchema):
    """Schema for pagination parameters"""
    
    page = fields.Int(required=False, validate=validate.Range(min=1))
    per_page = fields.Int(required=False, validate=validate.Range(min=1, max=100))
    sort_by = fields.Str(allow_none=True)
    sort_order = fields.Str(required=False, validate=validate.OneOf(['asc', 'desc']))

class SearchSchema(BaseSchema):
    """Schema for search parameters"""
    
    query = fields.Str(allow_none=True)
    filters = fields.Dict(allow_none=True)
    date_from = fields.DateTime(allow_none=True)
    date_to = fields.DateTime(allow_none=True)

# Response schemas for API responses
class SuccessResponseSchema(BaseSchema):
    """Schema for successful API responses"""
    
    success = fields.Bool(required=False, allow_none=True)
    message = fields.Str(allow_none=True)
    data = fields.Raw(allow_none=True)

class ErrorResponseSchema(BaseSchema):
    """Schema for error API responses"""
    
    success = fields.Bool(required=False, allow_none=True)
    error = fields.Str(required=True)
    details = fields.Dict(allow_none=True)

class PaginatedResponseSchema(BaseSchema):
    """Schema for paginated API responses"""
    
    success = fields.Bool(required=False, allow_none=True)
    data = fields.List(fields.Raw())
    pagination = fields.Dict()
    total = fields.Int()
    page = fields.Int()
    per_page = fields.Int()
    pages = fields.Int()