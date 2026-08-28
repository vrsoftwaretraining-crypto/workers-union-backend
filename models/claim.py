from datetime import datetime

from database.db import db


class Claim(db.Model):
    """A benefit / insurance / accident-compensation record for a worker.

    Two ways a row gets created:
      1. Worker submits a claim request (status starts at 'Submitted') --
         e.g. "I had an accident on site, requesting compensation."
      2. Admin directly logs a benefit the union has already processed for
         a member (status can be set straight to 'Approved' or 'Paid') --
         e.g. recording that an insurance payout was arranged.

    Either way, admin can review/approve/reject and mark as paid, and the
    worker can see the status and history from their own login.
    """

    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    union_id = db.Column(db.Integer, db.ForeignKey("unions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    claim_type = db.Column(db.String(20), nullable=False, default="Insurance")  # Insurance|Accident|Other
    incident_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.String(500), nullable=False)
    supporting_document_file = db.Column(db.String(255))

    amount_requested = db.Column(db.Float, nullable=True)
    amount_approved = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="Submitted")
    # Submitted -> UnderReview -> Approved|Rejected -> Paid

    admin_notes = db.Column(db.String(500))
    payment_date = db.Column(db.Date, nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)

    created_by_role = db.Column(db.String(10), nullable=False, default="worker")  # worker|admin
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "claim_type": self.claim_type,
            "incident_date": self.incident_date.isoformat() if self.incident_date else None,
            "description": self.description,
            "supporting_document_file": self.supporting_document_file,
            "amount_requested": self.amount_requested,
            "amount_approved": self.amount_approved,
            "status": self.status,
            "admin_notes": self.admin_notes,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "payment_reference": self.payment_reference,
            "created_by_role": self.created_by_role,
            "created_at": self.created_at.isoformat(),
        }
