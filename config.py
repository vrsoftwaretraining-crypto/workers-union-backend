import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = _bool(os.environ.get("FLASK_DEBUG"), default=False)
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(INSTANCE_DIR, "union.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "120")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "30")))
    JWT_TOKEN_LOCATION = ["headers"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), default=True)

    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB per upload
    ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

    BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(BASE_DIR, "backups"))
    os.makedirs(BACKUP_DIR, exist_ok=True)

    LOG_DIR = os.environ.get("LOG_DIR", os.path.join(BASE_DIR, "logs"))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    os.makedirs(LOG_DIR, exist_ok=True)

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    DEFAULT_LANGUAGE = "te"
    SUPPORTED_LANGUAGES = ["en", "te", "hi", "kn"]


class DevelopmentConfig(Config):
    ENV = "development"
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    ENV = "testing"
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    ENV = "production"
    DEBUG = False


CONFIG_MAP = {"development": DevelopmentConfig, "testing": TestingConfig, "production": ProductionConfig}


def get_config(name=None):
    name = name or os.environ.get("FLASK_ENV", "production")
    return CONFIG_MAP.get(name, ProductionConfig)
