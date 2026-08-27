from flask import Blueprint, jsonify
from sqlalchemy import text

from database.db import db

health = Blueprint("health", __name__)


@health.route("/health")
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return jsonify({"status": status, "database": db_ok}), (200 if db_ok else 503)
