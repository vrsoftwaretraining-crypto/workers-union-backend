import logging
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


def _allowed(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]


def save_upload(file_storage, union_reg_no, user_id, doc_type):
    """Save an uploaded card/document image or PDF under a per-union,
    per-user folder. Returns the relative path stored in the DB, or raises
    ValueError if the file is missing/invalid type."""
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided")

    if not _allowed(file_storage.filename):
        raise ValueError("Only PDF, JPG and PNG files are allowed")

    safe_union = secure_filename(str(union_reg_no))
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    filename = f"{doc_type}_{uuid.uuid4().hex}.{ext}"

    rel_dir = os.path.join(safe_union, str(user_id))
    abs_dir = os.path.join(current_app.config["UPLOAD_DIR"], rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    abs_path = os.path.join(abs_dir, filename)
    file_storage.save(abs_path)
    logger.info("Saved upload doc_type=%s union=%s user_id=%s -> %s", doc_type, union_reg_no, user_id, abs_path)

    return os.path.join(rel_dir, filename)


def delete_upload(rel_path):
    if not rel_path:
        return
    abs_path = os.path.join(current_app.config["UPLOAD_DIR"], rel_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
        logger.info("Deleted upload %s", abs_path)
