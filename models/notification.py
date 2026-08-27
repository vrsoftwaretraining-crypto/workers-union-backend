from datetime import datetime

from database.db import db


class Notification(db.Model):
    """A message broadcast by union admin (meeting / function / gathering /
    general announcement). Delivered as text; the client (web or Flutter
    app) reads it aloud using on-device text-to-speech (no server-side
    audio generation needed, works offline, no paid API required) -- so
    'voice based' notifications work for every language without extra
    infrastructure."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    union_id = db.Column(db.Integer, db.ForeignKey("unions.id"), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), default="general")  # meeting|function|general|urgent
    language = db.Column(db.String(5), default="te")

    event_datetime = db.Column(db.DateTime, nullable=True)  # optional: meeting/function date-time
    location = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "language": self.language,
            "event_datetime": self.event_datetime.isoformat() if self.event_datetime else None,
            "location": self.location,
            "created_at": self.created_at.isoformat(),
        }


class NotificationRead(db.Model):
    __tablename__ = "notification_reads"
    __table_args__ = (db.UniqueConstraint("notification_id", "user_id", name="uq_notif_user"),)

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey("notifications.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
