from datetime import datetime

from flask_login import UserMixin

from database.db import db


class User(db.Model, UserMixin):
    """A person inside a union: either role='admin' (union office bearer /
    manager) or role='worker' (rank-and-file member)."""

    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("union_id", "username", name="uq_union_username"),
    )

    id = db.Column(db.Integer, primary_key=True)
    union_id = db.Column(db.Integer, db.ForeignKey("unions.id"), nullable=False, index=True)

    role = db.Column(db.String(10), nullable=False, default="worker")  # 'admin' | 'worker'
    username = db.Column(db.String(50), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Approval workflow: a self-registered worker is 'pending' until an
    # admin approves them, since their profile can include bank/health data.
    status = db.Column(db.String(15), nullable=False, default="pending")  # pending|approved|rejected|disabled

    full_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(250))
    phone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(120), nullable=True)

    worker_type = db.Column(db.String(50))  # Plumber, Electrician, etc.
    experience_years = db.Column(db.Float)

    health_card_no = db.Column(db.String(50))
    health_card_file = db.Column(db.String(255))
    health_card_status = db.Column(db.String(20), default="Not Submitted")

    union_card_id_no = db.Column(db.String(50))
    union_card_file = db.Column(db.String(255))

    labour_card_no = db.Column(db.String(50))  # e-Shram / labour card number
    labour_card_file = db.Column(db.String(255))
    labour_card_status = db.Column(db.String(20), default="Not Submitted")

    bank_account_no = db.Column(db.String(30))
    bank_ifsc = db.Column(db.String(15))
    bank_name = db.Column(db.String(100))

    nominee_name = db.Column(db.String(100))
    nominee_relation = db.Column(db.String(50))

    insurance_provider = db.Column(db.String(100))
    insurance_policy_no = db.Column(db.String(50))
    insurance_status = db.Column(db.String(20), default="Not Enrolled")

    language = db.Column(db.String(5), default="te")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_active(self):
        return self.status == "approved"

    def get_id(self):
        # Flask-Login needs a globally unique id string; user id alone is
        # already the primary key so this is fine.
        return str(self.id)

    def to_directory_dict(self):
        """Limited-field view shown to OTHER members (privacy-safe)."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "worker_type": self.worker_type,
            "experience_years": self.experience_years,
            "phone": self.phone,
        }

    def to_full_dict(self):
        """Full-field view shown only to the worker themself / union admin."""
        return {
            "id": self.id,
            "role": self.role,
            "status": self.status,
            "full_name": self.full_name,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "worker_type": self.worker_type,
            "experience_years": self.experience_years,
            "health_card_no": self.health_card_no,
            "health_card_file": self.health_card_file,
            "health_card_status": self.health_card_status,
            "union_card_id_no": self.union_card_id_no,
            "union_card_file": self.union_card_file,
            "labour_card_no": self.labour_card_no,
            "labour_card_file": self.labour_card_file,
            "labour_card_status": self.labour_card_status,
            "bank_account_no": self.bank_account_no,
            "bank_ifsc": self.bank_ifsc,
            "bank_name": self.bank_name,
            "nominee_name": self.nominee_name,
            "nominee_relation": self.nominee_relation,
            "insurance_provider": self.insurance_provider,
            "insurance_policy_no": self.insurance_policy_no,
            "insurance_status": self.insurance_status,
            "language": self.language,
        }
