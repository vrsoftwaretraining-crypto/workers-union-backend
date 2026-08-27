from flask import Blueprint, redirect, request, session, url_for
from flask_login import current_user

from database.db import db

language = Blueprint("language", __name__)

SUPPORTED = ("en", "te", "hi", "kn")


@language.route("/language/<lang>")
def change_language(lang):
    if lang in SUPPORTED:
        session["language"] = lang
        if current_user.is_authenticated:
            current_user.language = lang
            db.session.commit()
    return redirect(request.referrer or url_for("auth.login_page"))
