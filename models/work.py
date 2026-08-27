from datetime import datetime

from database.db import db


class WorkEntry(db.Model):
    """A day/job of work logged by a worker (site, hours, description)."""

    __tablename__ = "work_entries"

    id = db.Column(db.Integer, primary_key=True)
    union_id = db.Column(db.Integer, db.ForeignKey("unions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    work_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(250), nullable=False)
    location = db.Column(db.String(150))
    hours_worked = db.Column(db.Float)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "work_date": self.work_date.isoformat(),
            "description": self.description,
            "location": self.location,
            "hours_worked": self.hours_worked,
        }


class Transaction(db.Model):
    """Income / expense entry logged by a worker for their own records."""

    __tablename__ = "worker_transactions"

    id = db.Column(db.Integer, primary_key=True)
    union_id = db.Column(db.Integer, db.ForeignKey("unions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    kind = db.Column(db.String(10), nullable=False)  # Income | Expense
    category = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "category": self.category,
            "amount": self.amount,
            "transaction_date": self.transaction_date.isoformat(),
            "notes": self.notes,
        }
