import logging
from datetime import date, datetime

from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request,
    send_file, session, url_for
)
from flask_login import current_user, login_required

from database.db import db
from models.notification import Notification, NotificationRead
from models.user import User
from models.work import Transaction, WorkEntry
from services.auth_helpers import api_login_required, worker_required
from services.file_service import save_upload
from services.report_service import build_worker_excel_report, build_worker_pdf_report

logger = logging.getLogger(__name__)
worker = Blueprint("worker", __name__)


def _totals(transactions):
    income = sum(t.amount for t in transactions if t.kind == "Income")
    expense = sum(t.amount for t in transactions if t.kind == "Expense")
    return {"income": income, "expense": expense, "net": income - expense}


# =====================================================
# DASHBOARD
# =====================================================
@worker.route("/dashboard")
@login_required
@worker_required
def dashboard():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    totals = _totals(transactions)
    recent_notifications = (
        Notification.query.filter_by(union_id=current_user.union_id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "worker_dashboard.html", user=current_user, totals=totals, notifications=recent_notifications
    )


# =====================================================
# MEMBER DIRECTORY (limited fields for privacy)
# =====================================================
@worker.route("/members")
@login_required
@worker_required
def members():
    all_members = (
        User.query.filter_by(union_id=current_user.union_id, role="worker", status="approved")
        .order_by(User.full_name)
        .all()
    )
    return render_template("worker_members.html", user=current_user, members=all_members)


# =====================================================
# NOTIFICATIONS
# =====================================================
@worker.route("/notifications")
@login_required
@worker_required
def notifications():
    all_notifications = (
        Notification.query.filter_by(union_id=current_user.union_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    read_ids = {
        r.notification_id
        for r in NotificationRead.query.filter_by(user_id=current_user.id).all()
    }
    return render_template(
        "worker_notifications.html", user=current_user, notifications=all_notifications, read_ids=read_ids
    )


@worker.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
@worker_required
def mark_notification_read(notification_id):
    exists = NotificationRead.query.filter_by(
        notification_id=notification_id, user_id=current_user.id
    ).first()
    if not exists:
        db.session.add(NotificationRead(notification_id=notification_id, user_id=current_user.id))
        db.session.commit()
    return ("", 204)


# =====================================================
# MY CARDS (own health/union/labour/insurance/bank details)
# =====================================================
@worker.route("/my-cards", methods=["GET", "POST"])
@login_required
@worker_required
def my_cards():
    if request.method == "POST":
        try:
            for field, doc_type in (
                ("health_card_file", "health_card"),
                ("union_card_file", "union_card"),
                ("labour_card_file", "labour_card"),
            ):
                file_storage = request.files.get(field)
                if file_storage and file_storage.filename:
                    rel_path = save_upload(
                        file_storage,
                        union_reg_no=current_user.union.registration_no,
                        user_id=current_user.id,
                        doc_type=doc_type,
                    )
                    setattr(current_user, field, rel_path)
                    if field == "health_card_file":
                        current_user.health_card_status = "Submitted"
                    if field == "labour_card_file":
                        current_user.labour_card_status = "Submitted"
            db.session.commit()
            flash("Documents updated.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
        return redirect(url_for("worker.my_cards"))

    return render_template("worker_cards.html", user=current_user)


# =====================================================
# WORK ENTRIES
# =====================================================
@worker.route("/work-entries", methods=["GET", "POST"])
@login_required
@worker_required
def work_entries():
    if request.method == "POST":
        try:
            entry = WorkEntry(
                union_id=current_user.union_id,
                user_id=current_user.id,
                work_date=datetime.strptime(request.form["work_date"], "%Y-%m-%d").date(),
                description=request.form["description"].strip(),
                location=request.form.get("location", "").strip() or None,
                hours_worked=float(request.form["hours_worked"]) if request.form.get("hours_worked") else None,
            )
            db.session.add(entry)
            db.session.commit()
            flash("Work entry saved.", "success")
        except (ValueError, KeyError):
            flash("Please enter a valid date and description.", "error")
        return redirect(url_for("worker.work_entries"))

    entries = (
        WorkEntry.query.filter_by(user_id=current_user.id)
        .order_by(WorkEntry.work_date.desc())
        .all()
    )
    return render_template("worker_work_entries.html", user=current_user, entries=entries, today=date.today())


@worker.route("/work-entries/<int:entry_id>/delete", methods=["POST"])
@login_required
@worker_required
def delete_work_entry(entry_id):
    entry = WorkEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash("Work entry removed.", "success")
    return redirect(url_for("worker.work_entries"))


# =====================================================
# TRANSACTIONS (income/expense)
# =====================================================
@worker.route("/transactions", methods=["GET", "POST"])
@login_required
@worker_required
def transactions():
    if request.method == "POST":
        try:
            item = Transaction(
                union_id=current_user.union_id,
                user_id=current_user.id,
                kind=request.form["kind"],
                category=request.form["category"].strip(),
                amount=float(request.form["amount"]),
                transaction_date=datetime.strptime(request.form["transaction_date"], "%Y-%m-%d").date(),
                notes=request.form.get("notes", "").strip() or None,
            )
            if item.kind not in ("Income", "Expense") or item.amount <= 0:
                raise ValueError
            db.session.add(item)
            db.session.commit()
            flash(f"{item.kind} entry saved.", "success")
        except (ValueError, KeyError):
            flash("Please enter a valid type, date, and positive amount.", "error")
        return redirect(url_for("worker.transactions"))

    entries = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )
    return render_template("worker_transactions.html", user=current_user, entries=entries, today=date.today())


@worker.route("/transactions/<int:entry_id>/delete", methods=["POST"])
@login_required
@worker_required
def delete_transaction(entry_id):
    entry = Transaction.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash("Entry removed.", "success")
    return redirect(url_for("worker.transactions"))


# =====================================================
# REPORTS + EXPORT
# =====================================================
@worker.route("/reports")
@login_required
@worker_required
def reports():
    transactions = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )
    entries = (
        WorkEntry.query.filter_by(user_id=current_user.id)
        .order_by(WorkEntry.work_date.desc())
        .all()
    )
    totals = _totals(transactions)
    return render_template(
        "worker_reports.html", user=current_user, transactions=transactions, entries=entries, totals=totals
    )


@worker.route("/reports/export/pdf")
@login_required
@worker_required
def export_pdf():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.transaction_date).all()
    entries = WorkEntry.query.filter_by(user_id=current_user.id).order_by(WorkEntry.work_date).all()
    totals = _totals(transactions)
    buf = build_worker_pdf_report(current_user, transactions, entries, totals)
    logger.info("Worker %s exported PDF report", current_user.username)
    return send_file(buf, as_attachment=True, download_name="worker_report.pdf", mimetype="application/pdf")


@worker.route("/reports/export/excel")
@login_required
@worker_required
def export_excel():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.transaction_date).all()
    entries = WorkEntry.query.filter_by(user_id=current_user.id).order_by(WorkEntry.work_date).all()
    totals = _totals(transactions)
    buf = build_worker_excel_report(current_user, transactions, entries, totals)
    logger.info("Worker %s exported Excel report", current_user.username)
    return send_file(
        buf, as_attachment=True, download_name="worker_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# =====================================================
# JSON API (Flutter mobile app)
# =====================================================
@worker.route("/api/me", methods=["GET"])
@api_login_required
def api_me(user):
    return jsonify({"success": True, "user": user.to_full_dict()})


@worker.route("/api/members", methods=["GET"])
@api_login_required
def api_members(user):
    all_members = User.query.filter_by(union_id=user.union_id, role="worker", status="approved").order_by(User.full_name).all()
    return jsonify({"success": True, "members": [m.to_directory_dict() for m in all_members]})


@worker.route("/api/notifications", methods=["GET"])
@api_login_required
def api_notifications(user):
    items = Notification.query.filter_by(union_id=user.union_id).order_by(Notification.created_at.desc()).all()
    read_ids = {r.notification_id for r in NotificationRead.query.filter_by(user_id=user.id).all()}
    payload = []
    for n in items:
        d = n.to_dict()
        d["is_read"] = n.id in read_ids
        payload.append(d)
    return jsonify({"success": True, "notifications": payload})


@worker.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
@api_login_required
def api_mark_read(user, notification_id):
    exists = NotificationRead.query.filter_by(notification_id=notification_id, user_id=user.id).first()
    if not exists:
        db.session.add(NotificationRead(notification_id=notification_id, user_id=user.id))
        db.session.commit()
    return jsonify({"success": True})


@worker.route("/api/work-entries", methods=["GET", "POST"])
@api_login_required
def api_work_entries(user):
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        try:
            entry = WorkEntry(
                union_id=user.union_id,
                user_id=user.id,
                work_date=datetime.fromisoformat(data["work_date"]).date(),
                description=str(data["description"]).strip(),
                location=data.get("location"),
                hours_worked=data.get("hours_worked"),
            )
        except (KeyError, ValueError):
            return jsonify({"success": False, "message": "work_date and description are required"}), 400
        db.session.add(entry)
        db.session.commit()
        return jsonify({"success": True, "entry": entry.to_dict()})

    entries = WorkEntry.query.filter_by(user_id=user.id).order_by(WorkEntry.work_date.desc()).all()
    return jsonify({"success": True, "entries": [e.to_dict() for e in entries]})


@worker.route("/api/work-entries/<int:entry_id>", methods=["DELETE"])
@api_login_required
def api_delete_work_entry(user, entry_id):
    entry = WorkEntry.query.filter_by(id=entry_id, user_id=user.id).first()
    if not entry:
        return jsonify({"success": False, "message": "Not found"}), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"success": True})


@worker.route("/api/transactions", methods=["GET", "POST"])
@api_login_required
def api_transactions(user):
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        try:
            item = Transaction(
                union_id=user.union_id,
                user_id=user.id,
                kind=data["kind"],
                category=str(data["category"]).strip(),
                amount=float(data["amount"]),
                transaction_date=datetime.fromisoformat(data["transaction_date"]).date(),
                notes=data.get("notes"),
            )
            if item.kind not in ("Income", "Expense") or item.amount <= 0:
                raise ValueError
        except (KeyError, ValueError):
            return jsonify({"success": False, "message": "Invalid transaction payload"}), 400
        db.session.add(item)
        db.session.commit()
        return jsonify({"success": True, "entry": item.to_dict()})

    entries = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.transaction_date.desc()).all()
    return jsonify({"success": True, "entries": [e.to_dict() for e in entries]})


@worker.route("/api/transactions/<int:entry_id>", methods=["DELETE"])
@api_login_required
def api_delete_transaction(user, entry_id):
    entry = Transaction.query.filter_by(id=entry_id, user_id=user.id).first()
    if not entry:
        return jsonify({"success": False, "message": "Not found"}), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"success": True})


@worker.route("/api/reports/summary", methods=["GET"])
@api_login_required
def api_reports_summary(user):
    transactions = Transaction.query.filter_by(user_id=user.id).all()
    totals = _totals(transactions)
    return jsonify({"success": True, "totals": totals})


@worker.route("/api/reports/export/pdf", methods=["GET"])
@api_login_required
def api_export_pdf(user):
    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.transaction_date).all()
    entries = WorkEntry.query.filter_by(user_id=user.id).order_by(WorkEntry.work_date).all()
    totals = _totals(transactions)
    buf = build_worker_pdf_report(user, transactions, entries, totals)
    return send_file(buf, as_attachment=True, download_name="worker_report.pdf", mimetype="application/pdf")


@worker.route("/api/reports/export/excel", methods=["GET"])
@api_login_required
def api_export_excel(user):
    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.transaction_date).all()
    entries = WorkEntry.query.filter_by(user_id=user.id).order_by(WorkEntry.work_date).all()
    totals = _totals(transactions)
    buf = build_worker_excel_report(user, transactions, entries, totals)
    return send_file(
        buf, as_attachment=True, download_name="worker_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@worker.route("/api/language", methods=["POST"])
@api_login_required
def api_set_language(user):
    data = request.get_json(force=True, silent=True) or {}
    lang = data.get("language")
    if lang not in ("en", "te", "hi", "kn"):
        return jsonify({"success": False, "message": "Unsupported language"}), 400
    user.language = lang
    db.session.commit()
    return jsonify({"success": True})
