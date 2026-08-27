from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

SALT = "password-reset"


def generate_reset_token(user_id):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps({"user_id": user_id}, salt=SALT)


def verify_reset_token(token, max_age_seconds=1800):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        data = serializer.loads(token, salt=SALT, max_age=max_age_seconds)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None
