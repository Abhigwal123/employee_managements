"""
Role utility helpers for normalizing and comparing role values.
"""
from __future__ import annotations

from typing import Optional

# Canonical normalized role keys
CLIENT_ADMIN_ROLE = "clientadmin"
SYS_ADMIN_ROLE = "sysadmin"
SCHEDULE_MANAGER_ROLE = "schedulemanager"
EMPLOYEE_ROLE = "departmentemployee"

_ROLE_ALIAS_MAP = {
    "admin": CLIENT_ADMIN_ROLE,
    "clientadmin": CLIENT_ADMIN_ROLE,
    "clientadministrator": CLIENT_ADMIN_ROLE,
    "client_admin": CLIENT_ADMIN_ROLE,
    "client-admin": CLIENT_ADMIN_ROLE,
    "sysadmin": SYS_ADMIN_ROLE,
    "sys_admin": SYS_ADMIN_ROLE,
    "sys-admin": SYS_ADMIN_ROLE,
    "schedulemanager": SCHEDULE_MANAGER_ROLE,
    "schedule_manager": SCHEDULE_MANAGER_ROLE,
    "schedule-manager": SCHEDULE_MANAGER_ROLE,
    "scheduler": SCHEDULE_MANAGER_ROLE,
    "departmentemployee": EMPLOYEE_ROLE,
    "department_employee": EMPLOYEE_ROLE,
    "department-employee": EMPLOYEE_ROLE,
    "employee": EMPLOYEE_ROLE,
    "viewer": EMPLOYEE_ROLE,
}

_ROLE_DISPLAY_NAMES = {
    CLIENT_ADMIN_ROLE: "ClientAdmin",
    SYS_ADMIN_ROLE: "SysAdmin",
    SCHEDULE_MANAGER_ROLE: "ScheduleManager",
    EMPLOYEE_ROLE: "Department_Employee",
}

ROLE_HIERARCHY = [
    CLIENT_ADMIN_ROLE,
    SYS_ADMIN_ROLE,
    SCHEDULE_MANAGER_ROLE,
    EMPLOYEE_ROLE,
]


def normalize_role(role: Optional[str]) -> str:
    """
    Normalize a role string by lowercasing, removing separators, and applying aliases.
    """
    if not role:
        return ""
    raw = str(role).strip().lower().replace(" ", "")
    raw = raw.replace("_", "").replace("-", "")
    return _ROLE_ALIAS_MAP.get(raw, raw)


def is_client_admin_role(role: Optional[str]) -> bool:
    """Return True if the role represents a ClientAdmin."""
    return normalize_role(role) == CLIENT_ADMIN_ROLE


def is_sys_admin_role(role: Optional[str]) -> bool:
    """Return True if the role represents a SysAdmin (elevated but not full admin)."""
    return normalize_role(role) == SYS_ADMIN_ROLE


def is_schedule_manager_role(role: Optional[str]) -> bool:
    """Return True if the role represents a ScheduleManager."""
    return normalize_role(role) == SCHEDULE_MANAGER_ROLE


def is_employee_role(role: Optional[str]) -> bool:
    """Return True if the role represents any employee-level account."""
    return normalize_role(role) == EMPLOYEE_ROLE


def role_in_hierarchy(role: Optional[str]) -> int:
    """
    Return the index of the role inside the ROLE_HIERARCHY list
    (lower value = higher privilege). Unknown roles get the lowest priority.
    """
    normalized = normalize_role(role)
    try:
        return ROLE_HIERARCHY.index(normalized)
    except ValueError:
        return len(ROLE_HIERARCHY)


def format_role_for_response(role: Optional[str]) -> str:
    """
    Convert an internal role value into the canonical response string.
    Falls back to the original role if no mapping exists.
    """
    normalized = normalize_role(role)
    if not normalized:
        return role or ""
    return _ROLE_DISPLAY_NAMES.get(normalized, role or "")

