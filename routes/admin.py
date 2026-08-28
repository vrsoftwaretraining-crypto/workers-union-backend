import logging
import os
from datetime import date, datetime

from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
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
from services.file_service import save_upload
from werkzeug.security import generate_password_hash
from models.claim import Claim

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


@admin.route("/files/<path:relpath>")
@login_required
@admin_required
def view_file(relpath):
    """Serves an uploaded worker document (photo/health/union/labour/
    insurance card). Restricted to files inside the logged-in admin's own
    union folder, with a path-traversal guard, so one union's admin can
    never read another union's documents."""
    upload_root = os.path.abspath(current_app.config["UPLOAD_DIR"])
    requested_path = os.path.abspath(os.path.join(upload_root, relpath))

    if not requested_path.startswith(upload_root + os.sep):
        abort(403)  # attempted path traversal (e.g. "../../etc/passwd")

    allowed_prefix = os.path.join(upload_root, current_user.union.registration_no) + os.sep
    if not requested_path.startswith(allowed_prefix):
        abort(403)  # file belongs to a different union

    if not os.path.isfile(requested_path):
        abort(404)

    return send_file(requested_path)


@admin.route("/workers/add", methods=["GET"])
@login_required
@admin_required
def add_worker_page():
    return render_template("admin_add_worker.html", user=current_user)


@admin.route("/workers/add", methods=["POST"])
@login_required
@admin_required
def add_worker():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()

    if not all([username, password, full_name, phone]):
        flash("Username, password, full name and phone are required.", "error")
        return redirect(url_for("admin.add_worker_page"))

    if User.query.filter_by(union_id=current_user.union_id, username=username).first():
        flash("This username is already used in your union. Choose another.", "error")
        return redirect(url_for("admin.add_worker_page"))

    def parse_date(field):
        raw = request.form.get(field, "").strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    # Admin is registering this member in person, having already verified
    # them -- so the account is approved immediately (no pending queue).
    new_worker = User(
        union_id=current_user.union_id,
        role="worker",
        username=username,
        password_hash=generate_password_hash(password),
        status="approved",
        full_name=full_name,
        address=request.form.get("address", "").strip() or None,
        phone=phone,
        email=request.form.get("email", "").strip() or None,
        worker_type=request.form.get("worker_type", "").strip() or None,
        experience_years=float(request.form["experience_years"]) if request.form.get("experience_years") else None,
        health_card_no=request.form.get("health_card_no", "").strip() or None,
        union_card_id_no=request.form.get("union_card_id_no", "").strip() or None,
        union_card_issue_date=parse_date("union_card_issue_date"),
        union_card_expiry_date=parse_date("union_card_expiry_date"),
        labour_card_no=request.form.get("labour_card_no", "").strip() or None,
        labour_card_issue_date=parse_date("labour_card_issue_date"),
        labour_card_expiry_date=parse_date("labour_card_expiry_date"),
        bank_account_no=request.form.get("bank_account_no", "").strip() or None,
        bank_ifsc=request.form.get("bank_ifsc", "").strip() or None,
        bank_name=request.form.get("bank_name", "").strip() or None,
        nominee_name=request.form.get("nominee_name", "").strip() or None,
        nominee_relation=request.form.get("nominee_relation", "").strip() or None,
        insurance_provider=request.form.get("insurance_provider", "").strip() or None,
        insurance_policy_no=request.form.get("insurance_policy_no", "").strip() or None,
        language=request.form.get("language", "te"),
        aadhar_no=request.form.get("aadhar_no", "").strip() or None,
        pan_no=request.form.get("pan_no", "").strip().upper() or None,
    )
    db.session.add(new_worker)
    db.session.flush()  # get new_worker.id for file storage paths

    _save_worker_documents(new_worker)
    db.session.commit()

    logger.info("Admin %s directly registered worker %s", current_user.username, username)
    flash(f"{new_worker.full_name} registered and approved.", "success")
    return redirect(url_for("admin.workers"))


def _save_worker_documents(worker_obj):
    """Shared helper: pulls any of the 5 optional document files from the
    current request and saves them onto worker_obj. Used by both Add Worker
    and Edit Worker so admins can (re)upload/renew documents from either
    screen."""
    file_fields = {
        "photo_file": "photo",
        "health_card_file": "health_card",
        "union_card_file": "union_card",
        "labour_card_file": "labour_card",
        "insurance_card_file": "insurance_card",
    }
    for model_field, doc_type in file_fields.items():
        file_storage = request.files.get(model_field)
        if file_storage and file_storage.filename:
            try:
                rel_path = save_upload(
                    file_storage,
                    union_reg_no=worker_obj.union.registration_no,
                    user_id=worker_obj.id,
                    doc_type=doc_type,
                )
                setattr(worker_obj, model_field, rel_path)
                if model_field == "health_card_file":
                    worker_obj.health_card_status = "Verified"
                if model_field == "labour_card_file":
                    worker_obj.labour_card_status = "Verified"
            except ValueError as exc:
                flash(f"{doc_type}: {exc}", "error")


@admin.route("/workers/<int:worker_id>/edit", methods=["GET"])
@login_required
@admin_required
def edit_worker_page(worker_id):
    worker = User.query.filter_by(id=worker_id, union_id=current_user.union_id, role="worker").first_or_404()
    return render_template("admin_edit_worker.html", user=current_user, worker=worker, today=date.today())


@admin.route("/workers/<int:worker_id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_worker(worker_id):
    worker = User.query.filter_by(id=worker_id, union_id=current_user.union_id, role="worker").first_or_404()

    def parse_date(field):
        raw = request.form.get(field, "").strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    worker.full_name = request.form.get("full_name", worker.full_name).strip()
    worker.address = request.form.get("address", "").strip() or None
    worker.phone = request.form.get("phone", worker.phone).strip()
    worker.email = request.form.get("email", "").strip() or None
    worker.worker_type = request.form.get("worker_type", "").strip() or None
    worker.experience_years = float(request.form["experience_years"]) if request.form.get("experience_years") else None
    worker.aadhar_no = request.form.get("aadhar_no", "").strip() or None
    worker.pan_no = request.form.get("pan_no", "").strip().upper() or None

    worker.health_card_no = request.form.get("health_card_no", "").strip() or None
    worker.union_card_id_no = request.form.get("union_card_id_no", "").strip() or None
    worker.union_card_issue_date = parse_date("union_card_issue_date")
    worker.union_card_expiry_date = parse_date("union_card_expiry_date")
    worker.labour_card_no = request.form.get("labour_card_no", "").strip() or None
    worker.labour_card_issue_date = parse_date("labour_card_issue_date")
    worker.labour_card_expiry_date = parse_date("labour_card_expiry_date")

    worker.bank_account_no = request.form.get("bank_account_no", "").strip() or None
    worker.bank_ifsc = request.form.get("bank_ifsc", "").strip() or None
    worker.bank_name = request.form.get("bank_name", "").strip() or None
    worker.nominee_name = request.form.get("nominee_name", "").strip() or None
    worker.nominee_relation = request.form.get("nominee_relation", "").strip() or None
    worker.insurance_provider = request.form.get("insurance_provider", "").strip() or None
    worker.insurance_policy_no = request.form.get("insurance_policy_no", "").strip() or None
    worker.insurance_status = request.form.get("insurance_status", worker.insurance_status)

    _save_worker_documents(worker)
    db.session.commit()

    logger.info("Admin %s updated worker %s (id=%s)", current_user.username, worker.username, worker.id)
    flash("Member details updated.", "success")
    return redirect(url_for("admin.edit_worker_page", worker_id=worker.id))


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


# =====================================================
# BENEFITS / CLAIMS (insurance, accident compensation)
# =====================================================
@admin.route("/claims")
@login_required
@admin_required
def claims():
    status_filter = request.args.get("status")
    query = Claim.query.filter_by(union_id=current_user.union_id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    all_claims = query.order_by(Claim.created_at.desc()).all()
    workers_by_id = {w.id: w for w in User.query.filter_by(union_id=current_user.union_id).all()}
    return render_template(
        "admin_claims.html", user=current_user, claims=all_claims,
        workers_by_id=workers_by_id, status_filter=status_filter, today=date.today(),
    )


@admin.route("/claims/add", methods=["POST"])
@login_required
@admin_required
def add_claim():
    worker_id = request.form.get("user_id", type=int)
    worker_obj = User.query.filter_by(id=worker_id, union_id=current_user.union_id, role="worker").first()
    if not worker_obj:
        flash("Select a valid member.", "error")
        return redirect(url_for("admin.claims"))

    def parse_date(field):
        raw = request.form.get(field, "").strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    claim = Claim(
        union_id=current_user.union_id,
        user_id=worker_obj.id,
        claim_type=request.form.get("claim_type", "Insurance"),
        incident_date=parse_date("incident_date"),
        description=request.form.get("description", "").strip() or "Recorded by union office",
        amount_requested=float(request.form["amount_requested"]) if request.form.get("amount_requested") else None,
        amount_approved=float(request.form["amount_approved"]) if request.form.get("amount_approved") else None,
        status=request.form.get("status", "Approved"),
        admin_notes=request.form.get("admin_notes", "").strip() or None,
        payment_date=parse_date("payment_date"),
        payment_reference=request.form.get("payment_reference", "").strip() or None,
        created_by_role="admin",
        processed_at=datetime.utcnow(),
        processed_by=current_user.id,
    )
    db.session.add(claim)
    db.session.commit()
    logger.info("Admin %s recorded a %s claim for worker_id=%s", current_user.username, claim.claim_type, worker_obj.id)
    flash("Benefit record added.", "success")
    return redirect(url_for("admin.claims"))


@admin.route("/claims/<int:claim_id>/update", methods=["POST"])
@login_required
@admin_required
def update_claim(claim_id):
    claim = Claim.query.filter_by(id=claim_id, union_id=current_user.union_id).first_or_404()

    claim.status = request.form.get("status", claim.status)
    claim.admin_notes = request.form.get("admin_notes", "").strip() or None
    if request.form.get("amount_approved"):
        claim.amount_approved = float(request.form["amount_approved"])
    if request.form.get("payment_date"):
        try:
            claim.payment_date = datetime.strptime(request.form["payment_date"], "%Y-%m-%d").date()
        except ValueError:
            pass
    claim.payment_reference = request.form.get("payment_reference", "").strip() or claim.payment_reference
    claim.processed_at = datetime.utcnow()
    claim.processed_by = current_user.id
    db.session.commit()

    logger.info("Admin %s updated claim #%s -> status=%s", current_user.username, claim.id, claim.status)
    flash("Claim updated.", "success")
    return redirect(url_for("admin.claims"))


@admin.route("/api/claims", methods=["GET"])
@api_admin_required
def api_list_claims(user):
    status_filter = request.args.get("status")
    query = Claim.query.filter_by(union_id=user.union_id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    all_claims = query.order_by(Claim.created_at.desc()).all()
    return jsonify({"success": True, "claims": [c.to_dict() for c in all_claims]})


@admin.route("/api/claims/<int:claim_id>/update", methods=["POST"])
@api_admin_required
def api_update_claim(user, claim_id):
    claim = Claim.query.filter_by(id=claim_id, union_id=user.union_id).first()
    if not claim:
        return jsonify({"success": False, "message": "Claim not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    claim.status = data.get("status", claim.status)
    claim.admin_notes = data.get("admin_notes", claim.admin_notes)
    if data.get("amount_approved") is not None:
        claim.amount_approved = data["amount_approved"]
    if data.get("payment_date"):
        try:
            claim.payment_date = datetime.fromisoformat(data["payment_date"]).date()
        except ValueError:
            pass
    claim.payment_reference = data.get("payment_reference", claim.payment_reference)
    claim.processed_at = datetime.utcnow()
    claim.processed_by = user.id
    db.session.commit()
    return jsonify({"success": True, "claim": claim.to_dict()})
