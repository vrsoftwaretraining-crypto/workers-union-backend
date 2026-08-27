import logging
from functools import wraps

from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_login import current_user

from models.user import User

logger = logging.getLogger(__name__)


# ---------------- Web (session / Flask-Login) ----------------
def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            return {"success": False, "message": "Admin access required"}, 403
        return view(*args, **kwargs)
    return wrapper


def worker_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "worker":
            return {"success": False, "message": "Worker access required"}, 403
        return view(*args, **kwargs)
    return wrapper


# ---------------- Mobile (JWT) ----------------
def get_api_user():
    verify_jwt_in_request()
    user_id = get_jwt_identity()
    return User.query.get(int(user_id)) if user_id else None


def api_login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = get_api_user()
        if not user or user.status != "approved":
            return jsonify({"success": False, "message": "Unauthorized"}), 401
        return view(user, *args, **kwargs)
    return wrapper


def api_admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = get_api_user()
        if not user or user.status != "approved" or user.role != "admin":
            return jsonify({"success": False, "message": "Admin access required"}), 403
        return view(user, *args, **kwargs)
    return wrapper
