import hmac
from functools import wraps
from typing import Optional, Tuple
import jwt
from flask import current_app, jsonify, request

from .extensions import db
from .models import User


def generate_token(user_id: int, role: str) -> str:
    """Generate a signed JWT token valid for 24 hours."""
    from datetime import datetime, timezone, timedelta
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    secret = current_app.config.get("SECRET_KEY", "development-only-change-me")
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    secret = current_app.config.get("SECRET_KEY", "development-only-change-me")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception:
        return None


def get_token_from_header() -> Optional[str]:
    """Extract Bearer token from Authorization header or X-Access-Token header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    x_token = request.headers.get("X-Access-Token", "")
    if x_token:
        return x_token.strip()
    return None


def get_current_user() -> Optional[User]:
    """Retrieve current User model instance if a valid token is present."""
    token = get_token_from_header()
    if not token:
        return None
    payload = decode_token(token)
    if not payload or "user_id" not in payload:
        return None
    user = db.session.get(User, payload["user_id"])
    return user


def require_user(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        if not token:
            return jsonify(
                success=False,
                message="Authentication required. Please log in."
            ), 401
        payload = decode_token(token)
        if not payload:
            return jsonify(
                success=False,
                message="Invalid or expired session. Please log in again."
            ), 401
        user = db.session.get(User, payload["user_id"])
        if not user:
            return jsonify(
                success=False,
                message="User account not found."
            ), 401
        request.current_user = user
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        if not token:
            return jsonify(
                success=False,
                message="Admin authentication required."
            ), 401
        payload = decode_token(token)
        if not payload:
            return jsonify(
                success=False,
                message="Invalid or expired admin session."
            ), 401
        if payload.get("role") != "ADMIN":
            return jsonify(
                success=False,
                message="Access denied. Admin privileges required."
            ), 403
        user = db.session.get(User, payload["user_id"])
        if not user or user.role != "ADMIN":
            return jsonify(
                success=False,
                message="Admin account verification failed."
            ), 403
        request.current_user = user
        return f(*args, **kwargs)

    return decorated
