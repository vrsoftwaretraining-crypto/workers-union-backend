"""Database backup and restore.

Backup: dumps every table to JSON and bundles it with the raw SQLite file
(if using SQLite) into one timestamped .zip under BACKUP_DIR.

Restore: validates the uploaded zip contains the expected manifest, then
replaces the current data. Restore is destructive by design (it is a
restore, not a merge) so it is admin-only and logged.
"""
import io
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime

from flask import current_app

from database.db import db
from models.union import Union
from models.user import User
from models.notification import Notification, NotificationRead
from models.work import WorkEntry, Transaction
from models.claim import Claim

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
APP_TAG = "workers-union-app-backup"

TABLES = {
    "unions": Union,
    "users": User,
    "notifications": Notification,
    "notification_reads": NotificationRead,
    "work_entries": WorkEntry,
    "worker_transactions": Transaction,
    "claims": Claim,
}


def _model_to_row(instance):
    row = {}
    for col in instance.__table__.columns:
        value = getattr(instance, col.name)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        row[col.name] = value
    return row


def create_backup(union_id=None):
    """Create a backup zip. If union_id is given, only that union's data is
    exported (tenant-scoped backup); otherwise a full system backup is made
    (super-admin use only)."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    scope = f"union{union_id}" if union_id else "full"
    zip_name = f"backup_{scope}_{timestamp}.zip"
    zip_path = os.path.join(current_app.config["BACKUP_DIR"], zip_name)

    dump = {"manifest": {"app": APP_TAG, "created_at": timestamp, "scope": scope, "union_id": union_id}}

    for table_name, model in TABLES.items():
        query = model.query
        if union_id is not None and hasattr(model, "union_id"):
            query = query.filter_by(union_id=union_id)
        elif union_id is not None and model is Union:
            query = query.filter_by(id=union_id)
        dump[table_name] = [_model_to_row(row) for row in query.all()]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(dump, ensure_ascii=False, indent=2))

    logger.info("Backup created: %s (scope=%s)", zip_path, scope)
    return zip_path


def restore_backup(file_storage):
    """Restore from an uploaded backup zip. Destructive: replaces rows for
    the tables/union included in the backup manifest."""
    data = file_storage.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if MANIFEST_NAME not in zf.namelist():
            raise ValueError("Invalid backup file: manifest.json not found")
        dump = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))

    manifest = dump.get("manifest", {})
    if manifest.get("app") != APP_TAG:
        raise ValueError("This file was not produced by Workers Union App backup")

    union_id = manifest.get("union_id")
    logger.warning("Restoring backup created_at=%s scope=%s union_id=%s",
                    manifest.get("created_at"), manifest.get("scope"), union_id)

    # Delete existing rows for the affected scope, in FK-safe order.
    delete_order = ["notification_reads", "notifications", "work_entries",
                     "worker_transactions", "claims", "users", "unions"]
    for table_name in delete_order:
        model = TABLES[table_name]
        query = model.query
        if union_id is not None and hasattr(model, "union_id"):
            query = query.filter_by(union_id=union_id)
        elif union_id is not None and model is Union:
            query = query.filter_by(id=union_id)
        for row in query.all():
            db.session.delete(row)
    db.session.commit()

    # Re-insert in FK-safe order.
    insert_order = ["unions", "users", "notifications", "notification_reads",
                     "work_entries", "worker_transactions", "claims"]
    for table_name in insert_order:
        model = TABLES[table_name]
        for row in dump.get(table_name, []):
            clean_row = dict(row)
            for date_field in ("sowing_date", "transaction_date", "work_date", "event_datetime",
                               "created_at", "updated_at", "last_login_at", "read_at",
                               "incident_date", "payment_date", "processed_at",
                               "union_card_issue_date", "union_card_expiry_date",
                               "labour_card_issue_date", "labour_card_expiry_date"):
                if clean_row.get(date_field):
                    try:
                        if "T" in clean_row[date_field] or ":" in clean_row[date_field]:
                            clean_row[date_field] = datetime.fromisoformat(clean_row[date_field])
                        else:
                            clean_row[date_field] = datetime.fromisoformat(clean_row[date_field]).date()
                    except (ValueError, TypeError):
                        pass
            db.session.add(model(**clean_row))
    db.session.commit()
    logger.info("Restore complete for scope=%s union_id=%s", manifest.get("scope"), union_id)
    return manifest
