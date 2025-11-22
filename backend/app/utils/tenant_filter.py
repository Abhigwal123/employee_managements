"""
Tenant Filtering Utilities
Provides helper functions for automatic tenant-based data scoping
"""

from typing import Optional, TypeVar, Type
from sqlalchemy.orm import Query
from app.extensions import db
from app.utils.role_utils import is_client_admin_role
import logging

logger = logging.getLogger(__name__)

# Type variable for SQLAlchemy models
ModelType = TypeVar('ModelType')


def get_tenant_filtered_query(
    model_class: Type[ModelType],
    user,
    tenant_id_column: str = 'tenantID'
) -> Query:
    """
    Get a query filtered by tenant based on user role
    
    ClientAdmin users can see all data (no tenant filter).
    All other users (ScheduleManager, Employee) see only their tenant's data.
    
    Args:
        model_class: SQLAlchemy model class to query
        user: Current user object (must have 'role' and 'tenantID' attributes)
        tenant_id_column: Name of the tenant ID column in the model (default: 'tenantID')
        
    Returns:
        SQLAlchemy Query object filtered by tenant (if applicable)
        
    Example:
        # In a route:
        user = get_current_user()
        query = get_tenant_filtered_query(Department, user)
        departments = query.all()
    """
    query = model_class.query
    
    # ClientAdmin can see all data - no tenant filter
    if user and hasattr(user, 'role') and is_client_admin_role(user.role):
        logger.debug(f"Tenant filter: ClientAdmin user - returning unfiltered query for {model_class.__name__}")
        return query
    
    # All other roles are tenant-scoped
    if user and hasattr(user, 'tenantID') and user.tenantID:
        tenant_id = user.tenantID
        # Check if model has the tenant_id_column attribute
        if hasattr(model_class, tenant_id_column):
            filter_column = getattr(model_class, tenant_id_column)
            query = query.filter(filter_column == tenant_id)
            logger.debug(f"Tenant filter: Filtering {model_class.__name__} by tenantID={tenant_id}")
        else:
            logger.warning(f"Model {model_class.__name__} does not have column '{tenant_id_column}' - returning unfiltered query")
    else:
        logger.warning(f"User does not have tenantID - returning unfiltered query for {model_class.__name__}")
    
    return query


def ensure_tenant_id(entity, user, tenant_id_column: str = 'tenantID'):
    """
    Ensure an entity has the correct tenant_id set based on the current user
    
    This is useful when creating new entities to ensure they're assigned to the correct tenant.
    ClientAdmin users can still set tenant_id manually, but other roles will have it set to their tenant.
    
    Args:
        entity: Entity instance to set tenant_id on
        user: Current user object
        tenant_id_column: Name of the tenant ID column (default: 'tenantID')
        
    Example:
        # When creating a new department:
        dept = Department(name="New Dept")
        ensure_tenant_id(dept, current_user)
        db.session.add(dept)
    """
    if not entity:
        return
    
    if not hasattr(entity, tenant_id_column):
        logger.warning(f"Entity {type(entity).__name__} does not have column '{tenant_id_column}'")
        return
    
    # ClientAdmin can set tenant_id manually, but for other roles, enforce their tenant
    if user and hasattr(user, 'role') and not is_client_admin_role(user.role):
        if user and hasattr(user, 'tenantID') and user.tenantID:
            current_tenant_id = getattr(entity, tenant_id_column, None)
            if not current_tenant_id:
                setattr(entity, tenant_id_column, user.tenantID)
                logger.debug(f"Set {tenant_id_column}={user.tenantID} on {type(entity).__name__}")
            elif current_tenant_id != user.tenantID:
                # User is trying to create entity for a different tenant - this should be blocked
                logger.warning(f"User {user.username} (tenant={user.tenantID}) tried to create {type(entity).__name__} with tenant={current_tenant_id}")
                raise ValueError(f"Users can only create entities for their own tenant")
    
    # For ClientAdmin, if tenant_id is not set, we could set a default or leave it
    # For now, we'll leave it as-is to allow ClientAdmin flexibility


def get_user_tenant_id(user) -> Optional[str]:
    """
    Get tenant ID from user, handling ClientAdmin case
    
    Args:
        user: User object
        
    Returns:
        Tenant ID string, or None if user is ClientAdmin or doesn't have tenantID
    """
    if not user:
        return None
    
    if hasattr(user, 'role') and is_client_admin_role(user.role):
        return None  # ClientAdmin can access all tenants
    
    if hasattr(user, 'tenantID'):
        return user.tenantID
    
    return None


def is_client_admin(user) -> bool:
    """
    Check if user is a ClientAdmin (platform admin)
    
    Args:
        user: User object
        
    Returns:
        True if user is ClientAdmin, False otherwise
    """
    if not user:
        return False
    
    return hasattr(user, 'role') and is_client_admin_role(user.role)


