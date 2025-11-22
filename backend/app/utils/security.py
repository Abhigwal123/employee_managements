# Security Utilities
import bcrypt
import secrets
import string
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {str(e)}")
        raise

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        password: Plain text password
        hashed_password: Hashed password to verify against
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False

def generate_secure_token(length: int = 32) -> str:
    """
    Generate a secure random token
    
    Args:
        length: Length of the token
        
    Returns:
        Secure random token string
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_user_id() -> str:
    """Generate a unique user ID"""
    return f"user_{generate_secure_token(12)}"

def generate_tenant_id() -> str:
    """Generate a unique tenant ID"""
    return f"tenant_{generate_secure_token(12)}"

def generate_department_id() -> str:
    """Generate a unique department ID"""
    return f"dept_{generate_secure_token(12)}"

def generate_schedule_definition_id() -> str:
    """Generate a unique schedule definition ID"""
    return f"schedule_{generate_secure_token(12)}"

def generate_permission_id() -> str:
    """Generate a unique permission ID"""
    return f"perm_{generate_secure_token(12)}"

def generate_job_log_id() -> str:
    """Generate a unique job log ID"""
    return f"job_{generate_secure_token(12)}"

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    return True, ""

def sanitize_input(input_string: str) -> str:
    """
    Sanitize user input to prevent injection attacks
    
    Args:
        input_string: Input string to sanitize
        
    Returns:
        Sanitized string
    """
    if not input_string:
        return ""
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`']
    sanitized = input_string
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    return sanitized.strip()

def validate_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid, False otherwise
    """
    import re
    
    pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?$'
    return re.match(pattern, url) is not None


































