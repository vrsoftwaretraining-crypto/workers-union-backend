import logging
from datetime import datetime

from flask import (
    Blueprint, current_app, flash, jsonify, redirect, render_template,
    request, send_file, url_for
)
from flask_login import current_user, login_required

from database.db import db
from models.user import User
from models.notification import Notification
from models.work import Transaction, WorkEntry
from services.auth_helpers import admin_required, api_admin_required
from services.backup_service import create_backup, restore_backup
from services.notification_service import create_notification

logger = logging.getLogger(__name__)
admin = Blueprint("admin", __name__, url_prefix="/admin")


def _summary_for_union(union_id):
    workers = User.query.filter_by(union_id=union_id, role="worker").all()
    income = db.session.query(db.func.sum(Transaction.amount)).filter_by(
        union_id=union_id, kind="Income"
    ).scalar() or 0
    expense = db.session.query(db.func.sum(Transaction.amount)).filter_by(
        union_id=union_id, kind="Expense"
    ).scalar() or 0
    return {
        "total_workers": len(workers),
        "pending_workers": len([w for w in workers if w.status == "pending"]),
        "approved_workers": len([w for w in workers if w.status == "approved"]),
        "total_income": income,
        "total_expense": expense,
    }


# =====================================================
# WEB DASHBOARD
# =====================================================
@admin.route("/dashboard")
@login_required
@admin_required
def dashboard():
    summary = _summary_for_union(current_user.union_id)
    recent_notifications = (
        Notification.query.filter_by(union_id=current_user.union_id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template("admin_dashboard.html", user=current_user, summary=summary,
                            notifications=recent_notifications)


# =====================================================
# WORKER MANAGEMENT
# =====================================================
@admin.route("/workers")
@login_required
@admin_required
def workers():
    all_workers = (
        User.query.filter_by(union_id=current_user.union_id, role="worker")
        .order_by(User.status.desc(), User.full_name)
        .all()
    )
    return render_template("admin_workers.html", user=current_user, workers=all_workers)


@admin.route("/workers/<int:worker_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_worker(worker_id):
    worker = User.query.filter_by(id=worker_id, union_id=current_user.union_id, role="worker").first_or_404()
    worker.status = "approved"
    db.session.commit()
    logger.info("Admin %s approved worker %s", current_user.username, worker.username)
    flash(f"{worker.full_name} approved.", "success")
    return redirect(url_for("admin.workers"))


@admin.route("/workers/<int:worker_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_worker(worker_id):
    worker = User.query.filter_by(id=worker_id, union_id=current_user.union_id, role="worker").first_or_404()
    worker.status = "rejected"
    db.session.commit()
    logger.info("Admin %s rejected worker %s", current_user.username, worker.username)
    flash(f"{worker.full_name} rejected.", "success")
    return redirect(url_for("admin.workers"))


@admin.route("/workers/<int:worker_id>/disable", methods=["POST"])
@login_required
@admin_required
def disable_worker(worker_id):
    worker = User.query.filter_by(id=worker_id, union_id=current_user.union_id, role="worker").first_or_404()
    worker.status = "disabled"
    db.session.commit()
    logger.info("Admin %s disabled worker %s", current_user.username, worker.username)
    flash(f"{worker.full_name} disabled.", "success")
    return redirect(url_for("admin.workers"))


@admin.route("/workers/<int:worker_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_worker(worker_id):
    worker = User.query.filter_by(id=worker_id, union_id=current_user.union_id, role="worker").first_or_404()
    db.session.delete(worker)
    db.session.commit()
    logger.warning("Admin %s deleted worker %s", current_user.username, worker.username)
    flash("Worker record deleted.", "success")
    return redirect(url_for("admin.workers"))


# =====================================================
# NOTIFICATIONS
# =====================================================
@admin.route("/notifications", methods=["GET", "POST"])
@login_required
@admin_required
def notifications():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        category = request.form.get("category", "general")
        language = request.form.get("language", "te")
        event_dt_raw = request.form.get("event_datetime", "").strip()
        event_dt = None
        if event_dt_raw:
            try:
                event_dt = datetime.strptime(event_dt_raw, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass

        if not title or not body:
            flash("Title and message are required.", "error")
        else:
            create_notification(
                union_id=current_user.union_id,
                created_by=current_user.id,
                title=title,
                body=body,
                category=category,
                language=language,
                event_datetime=event_dt,
                location=request.form.get("location", "").strip() or None,
            )
            flash("Notification sent to all union members.", "success")
        return redirect(url_for("admin.notifications"))

    all_notifications = (
        Notification.query.filter_by(union_id=current_user.union_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("admin_notifications.html", user=current_user, notifications=all_notifications)


# =====================================================
# BACKUP / RESTORE (web)
# =====================================================
@admin.route("/backup", methods=["GET"])
@login_required
@admin_required
def backup_page():
    return render_template("admin_backup.html", user=current_user)


@admin.route("/backup/download", methods=["POST"])
@login_required
@admin_required
def backup_download():
    zip_path = create_backup(union_id=current_user.union_id)
    logger.info("Admin %s downloaded a backup", current_user.username)
    return send_file(zip_path, as_attachment=True)


@admin.route("/backup/restore", methods=["POST"])
@login_required
@admin_required
def backup_restore():
    file_storage = request.files.get("backup_file")
    if not file_storage:
        flash("Please choose a backup .zip file.", "error")
        return redirect(url_for("admin.backup_page"))
    try:
        manifest = restore_backup(file_storage)
        flash(f"Restore complete (backup created at {manifest.get('created_at')}).", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception:
        logger.exception("Restore failed")
        flash("Restore failed. Check the backup file and try again.", "error")
    return redirect(url_for("admin.backup_page"))


# =====================================================
# JSON API (mobile / admin app parity)
# =====================================================
@admin.route("/api/workers", methods=["GET"])
@api_admin_required
def api_workers(user):
    all_workers = User.query.filter_by(union_id=user.union_id, role="worker").order_by(User.full_name).all()
    return jsonify({"success": True, "workers": [w.to_full_dict() for w in all_workers]})


@admin.route("/api/workers/<int:worker_id>/approve", methods=["POST"])
@api_admin_required
def api_approve_worker(user, worker_id):
    worker = User.query.filter_by(id=worker_id, union_id=user.union_id, role="worker").first()
    if not worker:
        return jsonify({"success": False, "message": "Worker not found"}), 404
    worker.status = "approved"
    db.session.commit()
    return jsonify({"success": True})


@admin.route("/api/notifications", methods=["POST"])
@api_admin_required
def api_send_notification(user):
    data = request.get_json(force=True, silent=True) or {}
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    if not title or not body:
        return jsonify({"success": False, "message": "Title and body are required"}), 400

    event_dt = None
    if data.get("event_datetime"):
        try:
            event_dt = datetime.fromisoformat(data["event_datetime"])
        except ValueError:
            pass

    notification = create_notification(
        union_id=user.union_id,
        created_by=user.id,
        title=title,
        body=body,
        category=data.get("category", "general"),
        language=data.get("language", "te"),
        event_datetime=event_dt,
        location=data.get("location"),
    )
    return jsonify({"success": True, "notification": notification.to_dict()})


@admin.route("/api/backup", methods=["POST"])
@api_admin_required
def api_backup(user):
    zip_path = create_backup(union_id=user.union_id)
    return send_file(zip_path, as_attachment=True)


@admin.route("/api/restore", methods=["POST"])
@api_admin_required
def api_restore(user):
    file_storage = request.files.get("backup_file")
    if not file_storage:
        return jsonify({"success": False, "message": "backup_file is required"}), 400
    try:
        manifest = restore_backup(file_storage)
        return jsonify({"success": True, "manifest": manifest})
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        logger.exception("Restore failed via API")
        return jsonify({"success": False, "message": "Restore failed"}), 500
