import logging
import os

from flask import Flask, jsonify, redirect, render_template, session, url_for

from config import get_config
from database.db import db
from extensions import login_manager, jwt, csrf, limiter
from logging_config import configure_logging


def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    configure_logging(app)
    logger = logging.getLogger(__name__)

    if app.config["SECRET_KEY"] == "dev-insecure-secret-key-change-me":
        logger.warning(
            "SECRET_KEY is using the INSECURE default. Set SECRET_KEY (and JWT_SECRET_KEY) "
            "as environment variables before deploying to production."
        )

    # --- extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"
    jwt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # JWT API routes are stateless (bearer token), so CSRF protection --
    # which is a cookie/session-based defense -- does not apply to them.
    # Web (session/cookie) routes keep CSRF protection.
    @app.before_request
    def _exempt_api_from_csrf():
        pass  # handled per-blueprint below via csrf.exempt

    from routes.auth import auth
    from routes.admin import admin
    from routes.worker import worker
    from routes.language import language
    from routes.health import health

    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(worker)
    app.register_blueprint(language)
    app.register_blueprint(health)

    # Exempt JSON/JWT API endpoints from CSRF (they use Bearer tokens, not
    # cookies, so CSRF does not apply and would otherwise block mobile
    # clients that can't supply a CSRF cookie/token).
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith(("/api/", "/admin/api/")):
            view = app.view_functions[rule.endpoint]
            csrf.exempt(view)

    from services.language_service import get_text
    from flask import session as flask_session

    def translate(key):
        lang = flask_session.get("language", app.config["DEFAULT_LANGUAGE"])
        return get_text(key, lang)

    app.jinja_env.globals.update(translate=translate)

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return db.session.get(User, int(user_id))

    # --- error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        logger.warning("403 Forbidden: %s", e)
        return render_template("error.html", code=403, message="You don't have access to that page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Unhandled server error")
        return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"success": False, "message": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"success": False, "message": "Invalid token"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({"success": False, "message": "Authorization token required"}), 401

    with app.app_context():
        from models.union import Union
        from models.user import User
        from models.notification import Notification, NotificationRead
        from models.work import WorkEntry, Transaction
        db.create_all()
        logger.info("Database tables verified/created")

    @app.route("/")
    def home():
        return redirect(url_for("auth.login_page"))

    logger.info("Workers Union App started (env=%s)", app.config["ENV"])
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=app.config["DEBUG"])
