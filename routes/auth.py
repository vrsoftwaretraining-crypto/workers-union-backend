import logging
from datetime import datetime, date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db
from extensions import limiter
from models.union import Union
from models.user import User
from services.token_service import generate_reset_token, verify_reset_token

logger = logging.getLogger(__name__)
auth = Blueprint("auth", __name__)


# =====================================================
# UNION REGISTRATION (creates union + its first admin)
# =====================================================
@auth.route("/register-union", methods=["GET"])
def register_union_page():
    return render_template("register_union.html")


@auth.route("/register-union", methods=["POST"])
@limiter.limit("5 per hour")
def register_union():
    reg_no = request.form.get("registration_no", "").strip()
    name = request.form.get("name", "").strip()
    admin_username = request.form.get("admin_username", "").strip()
    admin_password = request.form.get("admin_password", "")
    admin_full_name = request.form.get("admin_full_name", "").strip()
    admin_phone = request.form.get("admin_phone", "").strip()

    if not all([reg_no, name, admin_username, admin_password, admin_full_name, admin_phone]):
        flash("Please complete all fields.", "error")
        return redirect(url_for("auth.register_union_page"))

    if Union.query.filter_by(registration_no=reg_no).first():
        flash("A union with this registration number already exists.", "error")
        return redirect(url_for("auth.register_union_page"))

    union = Union(
        registration_no=reg_no,
        name=name,
        address=request.form.get("address", "").strip(),
        contact_phone=admin_phone,
        contact_email=request.form.get("contact_email", "").strip() or None,
    )
    db.session.add(union)
    db.session.flush()  # get union.id before commit

    admin = User(
        union_id=union.id,
        role="admin",
        username=admin_username,
        password_hash=generate_password_hash(admin_password),
        status="approved",
        full_name=admin_full_name,
        phone=admin_phone,
    )
    db.session.add(admin)
    db.session.commit()

    logger.info("New union registered: %s (%s), admin=%s", name, reg_no, admin_username)
    flash("Union registered successfully. Please log in.", "success")
    return redirect(url_for("auth.login_page"))


# =====================================================
# WEB LOGIN (admin + worker share the same login form)
# =====================================================
@auth.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html", lang=session.get("language", "te"))


@auth.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    reg_no = request.form.get("union_reg_no", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    union = Union.query.filter_by(registration_no=reg_no, is_active=True).first()
    user = (
        User.query.filter_by(union_id=union.id, username=username).first()
        if union else None
    )

    if not union or not user or not check_password_hash(user.password_hash, password):
        flash("Invalid union number, username, or password.", "error")
        return redirect(url_for("auth.login_page"))

    if user.status == "pending":
        flash("Your account is awaiting union admin approval.", "error")
        return redirect(url_for("auth.login_page"))
    if user.status in ("rejected", "disabled"):
        flash("Your account is not active. Please contact your union office.", "error")
        return redirect(url_for("auth.login_page"))

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    session["language"] = user.language
    session["union_id"] = user.union_id
    login_user(user)
    logger.info("User %s (union %s) logged in via web", user.username, union.registration_no)

    if user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("worker.dashboard"))


@auth.route("/logout")
def logout():
    if current_user.is_authenticated:
        logger.info("User %s logged out", current_user.username)
    session.clear()
    logout_user()
    return redirect(url_for("auth.login_page"))


# =====================================================
# FORGOT / RESET PASSWORD (web)
# =====================================================
@auth.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("forgot_password.html")


@auth.route("/forgot-password", methods=["POST"])
@limiter.limit("5 per hour")
def forgot_password():
    reg_no = request.form.get("union_reg_no", "").strip()
    username = request.form.get("username", "").strip()

    union = Union.query.filter_by(registration_no=reg_no).first()
    user = User.query.filter_by(union_id=union.id, username=username).first() if union else None

    # Always show the same message whether or not the account exists, to
    # avoid leaking which usernames/union numbers are registered.
    generic_message = (
        "If that account exists, a password reset link has been generated. "
        "Contact your union admin/office to retrieve it, or check your registered email."
    )

    if user:
        token = generate_reset_token(user.id)
        reset_url = url_for("auth.reset_password_page", token=token, _external=True)
        # No SMTP configured in this environment: log it so an admin/dev can
        # relay it manually. Wire up services/mail_service in production to
        # email this reset_url to user.email automatically.
        logger.info("Password reset requested for user_id=%s. Reset link: %s", user.id, reset_url)

    flash(generic_message, "success")
    return redirect(url_for("auth.login_page"))


@auth.route("/reset-password/<token>", methods=["GET"])
def reset_password_page(token):
    user_id = verify_reset_token(token)
    if not user_id:
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password_page"))
    return render_template("reset_password.html", token=token)


@auth.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    user_id = verify_reset_token(token)
    if not user_id:
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password_page"))

    new_password = request.form.get("new_password", "")
    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("auth.reset_password_page", token=token))

    user = User.query.get(user_id)
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    logger.info("Password reset completed for user_id=%s", user_id)

    flash("Password updated. Please log in.", "success")
    return redirect(url_for("auth.login_page"))


# =====================================================
# MOBILE (FLUTTER) JWT API
# =====================================================
@auth.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    reg_no = str(data.get("union_reg_no", "")).strip()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    union = Union.query.filter_by(registration_no=reg_no, is_active=True).first()
    user = User.query.filter_by(union_id=union.id, username=username).first() if union else None

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"success": False, "message": "Invalid credentials."}), 401
    if user.status == "pending":
        return jsonify({"success": False, "message": "Account awaiting admin approval."}), 403
    if user.status in ("rejected", "disabled"):
        return jsonify({"success": False, "message": "Account is not active."}), 403

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    logger.info("[API] User %s (union %s) logged in", user.username, reg_no)

    return jsonify({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_full_dict(),
    })


@auth.route("/api/refresh", methods=["POST"])
@jwt_required(refresh=True)
def api_refresh():
    identity = get_jwt_identity()
    new_token = create_access_token(identity=identity)
    return jsonify({"success": True, "access_token": new_token})


@auth.route("/api/forgot-password", methods=["POST"])
@limiter.limit("5 per hour")
def api_forgot_password():
    data = request.get_json(force=True, silent=True) or {}
    reg_no = str(data.get("union_reg_no", "")).strip()
    username = str(data.get("username", "")).strip()

    union = Union.query.filter_by(registration_no=reg_no).first()
    user = User.query.filter_by(union_id=union.id, username=username).first() if union else None

    if user:
        token = generate_reset_token(user.id)
        logger.info("[API] Password reset requested for user_id=%s. Token: %s", user.id, token)
        # In production, email/SMS this token (or a deep link containing it)
        # to the user via services/mail_service or an SMS provider.

    return jsonify({
        "success": True,
        "message": "If that account exists, a reset link/token has been generated for you.",
    })


@auth.route("/api/reset-password", methods=["POST"])
def api_reset_password():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token", "")
    new_password = str(data.get("new_password", ""))

    user_id = verify_reset_token(token)
    if not user_id:
        return jsonify({"success": False, "message": "Reset token invalid or expired."}), 400
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400

    user = User.query.get(user_id)
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    logger.info("[API] Password reset completed for user_id=%s", user_id)

    return jsonify({"success": True, "message": "Password updated."})
