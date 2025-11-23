"""
User Registration Helper Functions
Provides role-based permission checking for user registration
"""
from typing import Optional, Tuple
import logging

from ..models import User
from .role_utils import (
    EMPLOYEE_ROLE,
    ROLE_HIERARCHY,
    SCHEDULE_MANAGER_ROLE,
    format_role_for_response,
    is_client_admin_role,
    is_sys_admin_role,
    is_schedule_manager_role,
    normalize_role,
)

logger = logging.getLogger(__name__)


def can_register_role(registering_user: Optional[User], target_role: str) -> Tuple[bool, str]:
    """
    Check if a user can register another user with a specific role.

    Registration hierarchy (highest → lowest):
    - ClientAdmin → can register any role (including other ClientAdmins)
    - SysAdmin → can register ScheduleManager and DepartmentEmployee
    - ScheduleManager → can register DepartmentEmployee accounts
    - DepartmentEmployee/others → cannot register anyone
    - Public (no authenticated user) → not allowed
    """
    normalized_target_role = normalize_role(target_role)

    if normalized_target_role not in ROLE_HIERARCHY:
        return False, f"Unsupported role '{target_role}'"

    if not registering_user:
        return False, "Registration requires an authenticated user."

    normalized_registering_role = normalize_role(registering_user.role)

    if is_client_admin_role(normalized_registering_role):
        return True, ""

    if is_sys_admin_role(normalized_registering_role):
        if normalized_target_role in {SCHEDULE_MANAGER_ROLE, EMPLOYEE_ROLE}:
            return True, ""
        return False, "SysAdmin can only register ScheduleManager or DepartmentEmployee accounts."

    if is_schedule_manager_role(normalized_registering_role):
        if normalized_target_role == EMPLOYEE_ROLE:
            return True, ""
        return False, "ScheduleManager can only register Employee accounts."

    logger.warning(
        "Registration denied: role '%s' cannot register '%s'",
        registering_user.role,
        target_role,
    )
    readable_role = format_role_for_response(registering_user.role) or "Unknown role"
    if normalized_registering_role == EMPLOYEE_ROLE:
        return False, f"{readable_role} cannot register other users."

    return False, "Only ClientAdmin users can register new accounts."


def validate_role_hierarchy(registering_user: Optional[User], target_role: str) -> Tuple[bool, str]:
    """
    Alias retained for backward compatibility with earlier helpers.
    """
    return can_register_role(registering_user, target_role)

