import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(app):
    log_dir = app.config.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s (%(filename)s:%(lineno)d)"
    )

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "union_app.log"), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(log_level)

    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "error.log"), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    error_handler.setFormatter(fmt)
    error_handler.setLevel(logging.ERROR)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(log_level)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = [file_handler, error_handler, console_handler]
    app.logger.setLevel(log_level)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.logger.info("Logging configured (level=%s, dir=%s)", app.config.get("LOG_LEVEL"), log_dir)
