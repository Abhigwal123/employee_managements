from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt

from .role_utils import normalize_role


def role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required(optional=True)
        def wrapper(*args, **kwargs):
            # Skip auth check for OPTIONS requests (CORS preflight)
            from flask import request
            if request.method == "OPTIONS":
                return fn(*args, **kwargs)
            
            claims = get_jwt() or {}
            role = claims.get("role")
            
            normalized_role = normalize_role(role)
            normalized_allowed = [normalize_role(r) for r in allowed_roles]
            
            if allowed_roles and normalized_role not in normalized_allowed:
                return jsonify({"error": "forbidden", "reason": "insufficient_role"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator



