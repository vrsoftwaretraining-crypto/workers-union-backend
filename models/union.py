from datetime import datetime

from database.db import db


class Union(db.Model):
    """A worker union. All data (workers, notifications, work entries) is
    scoped to a union via union_id, so one deployment can safely host many
    unions with fully separated data."""

    __tablename__ = "unions"

    id = db.Column(db.Integer, primary_key=True)
    registration_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250))
    contact_phone = db.Column(db.String(15))
    contact_email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    users = db.relationship("User", backref="union", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "registration_no": self.registration_no,
            "name": self.name,
            "address": self.address,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
        }
