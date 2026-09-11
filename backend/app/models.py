from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_dt_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=True, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="USER", index=True)
    password_reset_token_hash = db.Column(db.String(255), nullable=True)
    password_reset_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    bookings = db.relationship("Booking", back_populates="user")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def as_api_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email or "",
            "phone": self.phone,
            "role": self.role,
            "created_at": format_dt_iso(self.created_at),
        }


class ParkingSlot(db.Model):
    __tablename__ = "parking_slots"

    id = db.Column(db.Integer, primary_key=True)
    slot_number = db.Column(db.String(10), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default="AVAILABLE", index=True)
    sensor_status = db.Column(db.String(20), nullable=False, default="EMPTY")
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    bookings = db.relationship("Booking", back_populates="slot")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def as_api_dict(self) -> dict:
        return {"slot": self.slot_number, "status": self.status.lower()}

    def as_admin_dict(self) -> dict:
        return {"slot": self.slot_number, "status": self.status.lower(), "sensor_status": self.sensor_status.lower()}



class Booking(db.Model):
    __tablename__ = "bookings"
    __table_args__ = (
        # MySQL permits multiple NULL values, so cancelled/completed rows do not
        # conflict. ACTIVE rows store their slot id here and must be unique.
        db.UniqueConstraint("active_slot_id", name="uq_bookings_active_slot"),
    )

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.String(20), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("parking_slots.id"), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    booking_time = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
    # This is NULL for non-active bookings and preserves a DB-level active-booking guard.
    active_slot_id = db.Column(db.Integer, nullable=True)
    entry_authorized = db.Column(db.Boolean, nullable=False, default=False)
    entry_time = db.Column(db.DateTime(timezone=True), nullable=True)
    exit_time = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    user = db.relationship("User", back_populates="bookings")
    slot = db.relationship("ParkingSlot", back_populates="bookings")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def as_api_dict(self) -> dict:
        return {
            "id": self.id,
            "booking_id": self.booking_id,
            "slot": self.slot.slot_number if self.slot else "",
            "slot_id": self.slot_id,
            "vehicle_number": self.vehicle_number,
            "status": self.status.lower(),
            "user_name": self.user.name if self.user else "",
            "user_email": self.user.email if self.user else "",
            "user_phone": self.user.phone if self.user else "",
            "entry_authorized": self.entry_authorized,
            "entry_time": format_dt_iso(self.entry_time),
            "exit_time": format_dt_iso(self.exit_time),
            "booking_time": format_dt_iso(self.booking_time),
            "created_at": format_dt_iso(self.created_at),
        }


class ParkingSystemState(db.Model):
    """Single persisted gate and vehicle-movement state."""

    __tablename__ = "parking_system_state"

    id = db.Column(db.Integer, primary_key=True)

    # Entry IR state
    entry_vehicle_waiting = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # Exit IR state
    exit_vehicle_waiting = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # Booking waiting to be consumed by ESP32
    pending_entry_booking_id = db.Column(
        db.Integer,
        nullable=True
    )

    # Vehicle movement state
    # IDLE
    # ENTERING
    # EXITING
    movement_state = db.Column(
        db.String(20),
        nullable=False,
        default="IDLE"
    )

    # During an EXITING sequence, this stores the slot
    # whose vehicle has started leaving.
    pending_exit_slot_id = db.Column(
        db.Integer,
        nullable=True
    )

    last_iot_update = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)