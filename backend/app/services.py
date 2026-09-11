from contextlib import contextmanager
from datetime import timedelta
import hashlib
import hmac
import logging
import re
import secrets
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

from .auth import generate_token
from .extensions import db
from .models import (
    Booking,
    ParkingSlot,
    ParkingSystemState,
    User,
    utcnow,
    format_dt_iso,
)

@contextmanager
def transaction_scope():
    session = db.session()
    if session.in_transaction():
        yield session
        session.commit()
    else:
        with session.begin():
            yield session




SLOT_PATTERN = re.compile(r"^S[1-3]$", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"^[0-9]{10}$")
VEHICLE_PATTERN = re.compile(r"^[A-Z0-9 -]{5,12}$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


# ============================================================
# STATE CONSTANTS
# ============================================================

MOVEMENT_IDLE = "IDLE"
MOVEMENT_ENTERING = "ENTERING"
MOVEMENT_EXITING = "EXITING"

SENSOR_EMPTY = "EMPTY"
SENSOR_OCCUPIED = "OCCUPIED"

SLOT_AVAILABLE = "AVAILABLE"
SLOT_RESERVED = "RESERVED"
SLOT_OCCUPIED = "OCCUPIED"
SLOT_EXITING = "EXITING"

# Debounce: how many seconds a slot sensor must consistently read EMPTY
# before triggering the exit sequence. Prevents false exits from brief
# sensor gaps (e.g. car repositioning).
SLOT_EXIT_DEBOUNCE_SECONDS = 2.0

# In-memory tracker: slot_number -> timestamp when sensor first went EMPTY.
# Reset to None when sensor reads OCCUPIED again.
import time as _time
_slot_empty_since: dict[str, float | None] = {}


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ============================================================
# USER AUTHENTICATION SERVICES
# ============================================================

def register_user(payload: object) -> User:
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).lower().strip()
    phone = str(payload.get("phone", "")).strip()
    password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", payload.get("confirmPassword", "")))

    if not 2 <= len(name) <= 100:
        raise ApiError("Name must contain between 2 and 100 characters.")
    if not EMAIL_PATTERN.fullmatch(email):
        raise ApiError("Please enter a valid email address.")
    if not PHONE_PATTERN.fullmatch(phone):
        raise ApiError("Phone must be a 10-digit mobile number.")
    if len(password) < 6:
        raise ApiError("Password must be at least 6 characters long.")
    if password != confirm_password:
        raise ApiError("Passwords do not match.")

    with transaction_scope():
        existing_email = db.session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

        if existing_email is not None and existing_email.password_hash:
            raise ApiError("Email is already registered. Please log in.", 409)

        # Check if user exists by phone (from quick booking)
        user = db.session.execute(
            select(User).where(User.phone == phone)
        ).scalars().first()

        if user is None:
            user = User(
                name=name,
                email=email,
                phone=phone,
                role="USER"
            )
            db.session.add(user)
        else:
            user.name = name
            user.email = email

        user.set_password(password)

    return user


def request_password_reset(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    email = str(payload.get("email", "")).lower().strip()
    if not email or not EMAIL_PATTERN.fullmatch(email):
        raise ApiError("Please enter a valid email address.")

    reset_token = None
    with transaction_scope():
        user = db.session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

        if user is not None:
            reset_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
            user.password_reset_token_hash = token_hash
            user.password_reset_expires_at = utcnow() + timedelta(hours=1)
            logger.info("RESET TOKEN GENERATED for user %s", user.email)

    resp = {
        "success": True,
        "message": "If an account exists for this email, password reset instructions have been sent."
    }
    if reset_token:
        resp["reset_token"] = reset_token

    return resp


def reset_password(payload: object) -> bool:
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    token = str(payload.get("token", "")).strip()
    new_password = str(payload.get("new_password", payload.get("newPassword", "")))
    confirm_password = str(payload.get("confirm_password", payload.get("confirmPassword", new_password)))

    if not token:
        raise ApiError("Password reset token is required.")

    if len(new_password) < 6:
        raise ApiError("Password must be at least 6 characters long.")

    if new_password != confirm_password:
        raise ApiError("Passwords do not match.")

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with transaction_scope():
        user = db.session.execute(
            select(User).where(User.password_reset_token_hash == token_hash)
        ).scalar_one_or_none()

        if user is None:
            raise ApiError("Invalid or expired password reset token.", 400)

        if user.password_reset_expires_at is not None:
            expires = user.password_reset_expires_at
            if expires.tzinfo is None:
                from datetime import timezone
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < utcnow():
                user.password_reset_token_hash = None
                user.password_reset_expires_at = None
                raise ApiError("Password reset token has expired.", 400)

        user.set_password(new_password)
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None

    return True


def login_user(payload: object) -> Tuple[User, str]:
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    email = str(payload.get("email", "")).lower().strip()
    password = str(payload.get("password", ""))

    if not email or not password:
        raise ApiError("Email and password are required.")

    user = db.session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    if user is None or not user.check_password(password):
        raise ApiError("Invalid email or password.", 401)

    token = generate_token(user.id, user.role)
    return user, token


def login_admin(payload: object) -> Tuple[dict, str]:
    from flask import current_app

    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    email = str(payload.get("email", "")).lower().strip()
    password = str(payload.get("password", ""))

    expected_email = current_app.config.get("ADMIN_EMAIL", "admin@parkease.com").lower().strip()
    expected_password = current_app.config.get("ADMIN_PASSWORD", "Admin123!")
    expected_hash = current_app.config.get("ADMIN_PASSWORD_HASH")

    valid_email = (email == expected_email)
    valid_password = False

    if expected_hash:
        from werkzeug.security import check_password_hash
        valid_password = check_password_hash(expected_hash, password)
    else:
        valid_password = hmac.compare_digest(password, expected_password)

    if not valid_email or not valid_password:
        raise ApiError("Invalid admin credentials.", 401)

    with transaction_scope():
        admin_user = db.session.execute(
            select(User).where(User.email == expected_email)
        ).scalar_one_or_none()

        if admin_user is None:
            admin_user = User(
                name="ParkEase Admin",
                email=expected_email,
                phone="0000000000",
                role="ADMIN"
            )
            admin_user.set_password(password)
            db.session.add(admin_user)
            db.session.flush()
        else:
            if admin_user.role != "ADMIN":
                admin_user.role = "ADMIN"

    token = generate_token(admin_user.id, "ADMIN")
    return {
        "id": admin_user.id,
        "name": admin_user.name,
        "email": admin_user.email,
        "role": "ADMIN"
    }, token


# ============================================================
# BOOKING VALIDATION
# ============================================================

def validate_booking_payload(payload: object, current_user: Optional[User] = None) -> dict:
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    if current_user is not None:
        name = current_user.name
        phone = current_user.phone
        email = current_user.email or ""
    else:
        name = str(payload.get("name", "")).strip()
        phone = str(payload.get("phone", "")).strip()
        email = str(payload.get("email", "")).strip()

    vehicle_number = re.sub(
        r"\s+",
        " ",
        str(payload.get("vehicle_number", "")).upper().strip()
    )

    slot_number = str(
        payload.get("slot", "") or payload.get("slot_number", "")
    ).upper().strip()

    if not 2 <= len(name) <= 100:
        raise ApiError("Name must contain between 2 and 100 characters.")

    if not PHONE_PATTERN.fullmatch(phone):
        raise ApiError("Phone must be a 10-digit mobile number.")

    if not VEHICLE_PATTERN.fullmatch(vehicle_number):
        raise ApiError("Vehicle number format is invalid.")

    if not SLOT_PATTERN.fullmatch(slot_number):
        raise ApiError("Slot must be one of S1, S2, or S3.")

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "vehicle_number": vehicle_number,
        "slot": slot_number,
    }


def _new_booking_id() -> str:
    return f"PE-{secrets.randbelow(900000) + 100000}"


# ============================================================
# CREATE BOOKING
# ============================================================

def create_booking(payload: object, current_user: Optional[User] = None) -> Booking:
    data = validate_booking_payload(payload, current_user=current_user)


    logger.info(
        "BOOK REQUEST slot=%s phone=%s vehicle=%s user=%s",
        data["slot"], data["phone"], data["vehicle_number"],
        current_user.id if current_user else "anonymous"
    )

    for attempt in range(3):
        try:
            with transaction_scope():
                # Lock requested slot
                slot = db.session.execute(
                    select(ParkingSlot)
                    .where(ParkingSlot.slot_number == data["slot"])
                    .with_for_update()
                ).scalar_one_or_none()

                if slot is None:
                    raise ApiError("Parking slot does not exist.", 404)

                if slot.status != SLOT_AVAILABLE:
                    raise ApiError(f"Slot {slot.slot_number} is no longer available.", 409)

                # Clean up stale active booking for this slot if any
                stale_booking = db.session.execute(
                    select(Booking)
                    .where(
                        Booking.active_slot_id == slot.id,
                        Booking.status == "ACTIVE",
                    )
                    .with_for_update()
                ).scalar_one_or_none()

                if stale_booking is not None:
                    logger.warning(
                        "STALE BOOKING %s still ACTIVE with active_slot_id=%s — completing it.",
                        stale_booking.booking_id, stale_booking.active_slot_id,
                    )
                    stale_booking.status = "COMPLETED"
                    stale_booking.active_slot_id = None
                    if stale_booking.exit_time is None:
                        stale_booking.exit_time = utcnow()

                # User selection / creation
                if current_user is not None:
                    user = db.session.execute(
                        select(User).where(User.id == current_user.id).with_for_update()
                    ).scalar_one()
                else:
                    user = db.session.execute(
                        select(User)
                        .where(User.phone == data["phone"])
                        .order_by(User.id.asc())
                        .with_for_update()
                    ).scalars().first()

                    if user is None:
                        user = User(
                            name=data["name"],
                            phone=data["phone"],
                            email=data["email"] or None,
                            role="USER"
                        )
                        db.session.add(user)
                        db.session.flush()
                    else:
                        user.name = data["name"]
                        if data["email"] and not user.email:
                            user.email = data["email"]

                # Enforce: User cannot have multiple active bookings simultaneously
                existing_active = db.session.execute(
                    select(Booking)
                    .where(
                        Booking.user_id == user.id,
                        Booking.status == "ACTIVE"
                    )
                    .with_for_update()
                ).scalars().first()

                if existing_active is not None:
                    raise ApiError("You already have an active booking.", 409)

                booking_id = _new_booking_id()

                booking = Booking(
                    booking_id=booking_id,
                    user_id=user.id,
                    slot_id=slot.id,
                    active_slot_id=slot.id,
                    vehicle_number=data["vehicle_number"],
                    status="ACTIVE",
                    entry_authorized=False,
                )

                slot.status = SLOT_RESERVED
                slot.sensor_status = SENSOR_EMPTY

                db.session.add(booking)
                db.session.flush()

            logger.info("BOOKING CREATED %s slot=%s", booking.booking_id, data["slot"])
            return booking

        except IntegrityError as exc:
            db.session.rollback()
            error_msg = str(exc.orig).lower() if exc.orig else str(exc).lower()
            logger.error("BOOKING FAILED attempt=%d IntegrityError: %s", attempt + 1, error_msg)

            if "booking_id" in error_msg or "ix_bookings_booking_id" in error_msg:
                continue

            if "active_slot" in error_msg or "uq_bookings_active_slot" in error_msg:
                raise ApiError(f"Slot {data['slot']} is no longer available.", 409)

            raise ApiError(
                "Unable to create booking due to a data conflict. Please try again.",
                409,
            )

    raise ApiError("Unable to generate a unique booking ID. Please try again.", 500)


# ============================================================
# CANCEL BOOKING
# ============================================================

def cancel_booking(booking_id: object, current_user: Optional[User] = None) -> Booking:
    normalized_id = str(booking_id or "").upper().strip()

    if not re.fullmatch(r"PE-[0-9]{6}", normalized_id):
        raise ApiError("A valid booking_id is required.")

    with transaction_scope():
        booking = db.session.execute(
            select(Booking)
            .where(Booking.booking_id == normalized_id)
            .with_for_update()
        ).scalar_one_or_none()

        if booking is None:
            raise ApiError("Booking not found.", 404)

        if current_user is not None and current_user.role != "ADMIN" and booking.user_id != current_user.id:
            raise ApiError("You do not have authorization to cancel this booking.", 403)

        if booking.status != "ACTIVE":
            raise ApiError("Booking is no longer active.", 409)

        slot = db.session.execute(
            select(ParkingSlot)
            .where(ParkingSlot.id == booking.slot_id)
            .with_for_update()
        ).scalar_one()

        if slot.status != SLOT_RESERVED:
            raise ApiError("Booking cannot be cancelled after parking has begun.", 409)

        booking.status = "CANCELLED"
        booking.active_slot_id = None

        slot.status = SLOT_AVAILABLE
        slot.sensor_status = SENSOR_EMPTY

    return booking


def _normalize_booking_id(booking_id: object) -> str:
    normalized_id = str(booking_id or "").upper().strip()
    if not re.fullmatch(r"PE-[0-9]{6}", normalized_id):
        raise ApiError("A valid booking_id is required.")
    return normalized_id


# ============================================================
# ENTRY SENSOR
# ============================================================

def report_entry_sensor(payload: object) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get("vehicle_waiting"), bool):
        raise ApiError("vehicle_waiting must be a boolean.")

    vehicle_waiting = payload["vehicle_waiting"]

    with transaction_scope():
        system_state = db.session.execute(
            select(ParkingSystemState).where(ParkingSystemState.id == 1).with_for_update()
        ).scalar_one_or_none()

        if system_state is None:
            raise ApiError("Parking gate state has not been initialized.", 503)

        system_state.entry_vehicle_waiting = vehicle_waiting
        if "exit_vehicle_waiting" in payload and isinstance(payload["exit_vehicle_waiting"], bool):
            system_state.exit_vehicle_waiting = payload["exit_vehicle_waiting"]
        system_state.last_iot_update = utcnow()

        if system_state.movement_state == MOVEMENT_EXITING:
            slot_id = system_state.pending_exit_slot_id

            if slot_id is None:
                fallback_slot = db.session.execute(
                    select(ParkingSlot)
                    .where(
                        ParkingSlot.status.in_([SLOT_EXITING, SLOT_OCCUPIED])
                    )
                    .with_for_update()
                ).scalars().first()

                if fallback_slot is not None:
                    fallback_slot.status = SLOT_EXITING
                    slot_id = fallback_slot.id
                    system_state.pending_exit_slot_id = slot_id

            # If vehicle is detected at outer gate sensor (vehicle_waiting == True while exiting),
            # it means the vehicle is physically passing through the gate to the outside now!
            if vehicle_waiting and slot_id is not None:
                slot = db.session.execute(
                    select(ParkingSlot).where(ParkingSlot.id == slot_id).with_for_update()
                ).scalar_one_or_none()

                if slot is not None:
                    booking = db.session.execute(
                        select(Booking)
                        .where(Booking.slot_id == slot.id, Booking.status == "ACTIVE")
                        .with_for_update()
                    ).scalar_one_or_none()

                    if booking is not None:
                        booking.status = "COMPLETED"
                        booking.active_slot_id = None
                        booking.exit_time = utcnow()

                    slot.status = SLOT_AVAILABLE
                    slot.sensor_status = SENSOR_EMPTY

                system_state.pending_exit_slot_id = None
                system_state.movement_state = MOVEMENT_IDLE
            elif system_state.exit_vehicle_waiting and slot_id is not None:
                # Vehicle is currently at the exit gate waiting/passing; keep slot as EXITING
                slot = db.session.execute(
                    select(ParkingSlot).where(ParkingSlot.id == slot_id).with_for_update()
                ).scalar_one_or_none()
                if slot is not None and slot.status != SLOT_AVAILABLE:
                    slot.status = SLOT_EXITING

    return vehicle_waiting


# ============================================================
# AUTHORIZE ENTRY
# ============================================================

def authorize_entry(booking_id: object, current_user: Optional[User] = None) -> Booking:
    normalized_id = _normalize_booking_id(booking_id)

    with transaction_scope():
        system_state = db.session.execute(
            select(ParkingSystemState).where(ParkingSystemState.id == 1).with_for_update()
        ).scalar_one_or_none()

        if system_state is None:
            raise ApiError("Parking gate state has not been initialized.", 503)

        booking = db.session.execute(
            select(Booking).where(Booking.booking_id == normalized_id).with_for_update()
        ).scalar_one_or_none()

        if booking is None or booking.status != "ACTIVE":
            raise ApiError("Booking is invalid or inactive.", 404)

        if current_user is not None and current_user.role != "ADMIN" and booking.user_id != current_user.id:
            raise ApiError("Your account does not match this booking.", 403)

        if booking.entry_authorized or booking.entry_time is not None:
            raise ApiError("Entry authorization has already been used.", 409)

        if not system_state.entry_vehicle_waiting:
            raise ApiError("Vehicle waiting at the entry sensor was not detected.", 409)

        if system_state.pending_entry_booking_id is not None:
            raise ApiError("Another entry authorization is already pending.", 409)

        if system_state.movement_state != MOVEMENT_IDLE:
            raise ApiError("Parking gate is currently handling another vehicle.", 409)

        slot = db.session.execute(
            select(ParkingSlot).where(ParkingSlot.id == booking.slot_id).with_for_update()
        ).scalar_one()

        if slot.status != SLOT_RESERVED:
            raise ApiError("Entry is allowed only for a reserved parking slot.", 409)

        booking.entry_authorized = True
        system_state.pending_entry_booking_id = booking.id

    return booking


# ============================================================
# CONSUME ENTRY AUTHORIZATION
# ============================================================

def consume_entry_authorization() -> dict:
    with transaction_scope():
        system_state = db.session.execute(
            select(ParkingSystemState).where(ParkingSystemState.id == 1).with_for_update()
        ).scalar_one_or_none()

        if system_state is None or system_state.pending_entry_booking_id is None:
            return {
                "authorized": False,
                "booking_id": None,
                "vehicle_number": None,
            }

        booking = db.session.execute(
            select(Booking)
            .where(Booking.id == system_state.pending_entry_booking_id)
            .with_for_update()
        ).scalar_one_or_none()

        if booking is None or not booking.entry_authorized or booking.status != "ACTIVE":
            system_state.pending_entry_booking_id = None
            return {
                "authorized": False,
                "booking_id": None,
                "vehicle_number": None,
            }

        booking.entry_authorized = False
        booking.entry_time = utcnow()

        system_state.movement_state = MOVEMENT_ENTERING
        system_state.pending_entry_booking_id = None
        system_state.entry_vehicle_waiting = False
        system_state.last_iot_update = utcnow()

        return {
            "authorized": True,
            "booking_id": booking.booking_id,
            "vehicle_number": booking.vehicle_number,
        }


# ============================================================
# ENTRY CROSSING COMPLETION
# ============================================================

def complete_entry_sequence() -> dict:
    with transaction_scope():
        system_state = db.session.execute(
            select(ParkingSystemState).where(ParkingSystemState.id == 1).with_for_update()
        ).scalar_one_or_none()

        if system_state is None:
            raise ApiError("Parking gate state has not been initialized.", 503)

        if system_state.movement_state == MOVEMENT_EXITING:
            slot_id = system_state.pending_exit_slot_id
            if slot_id is not None:
                slot = db.session.execute(
                    select(ParkingSlot).where(ParkingSlot.id == slot_id).with_for_update()
                ).scalar_one_or_none()

                if slot is not None:
                    booking = db.session.execute(
                        select(Booking)
                        .where(Booking.slot_id == slot.id, Booking.status == "ACTIVE")
                        .with_for_update()
                    ).scalar_one_or_none()

                    if booking is not None:
                        booking.status = "COMPLETED"
                        booking.active_slot_id = None
                        booking.exit_time = utcnow()

                    slot.status = SLOT_AVAILABLE
                    slot.sensor_status = SENSOR_EMPTY

            system_state.pending_exit_slot_id = None
            system_state.movement_state = MOVEMENT_IDLE
            system_state.entry_vehicle_waiting = False
            system_state.exit_vehicle_waiting = False
            system_state.last_iot_update = utcnow()

            return {
                "completed": True,
                "movement_state": MOVEMENT_IDLE,
            }

        if system_state.movement_state != MOVEMENT_ENTERING:
            return {
                "completed": False,
                "movement_state": system_state.movement_state,
            }

        system_state.movement_state = MOVEMENT_IDLE
        system_state.entry_vehicle_waiting = False
        system_state.last_iot_update = utcnow()

        return {
            "completed": True,
            "movement_state": MOVEMENT_IDLE,
        }


# ============================================================
# SLOT SENSOR REPORTING
# ============================================================

def report_slot_sensors(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    sensor_values = {}
    for slot_number in ("S1", "S2", "S3"):
        value = payload.get(slot_number)
        if not isinstance(value, bool):
            raise ApiError(f"{slot_number} sensor value must be a boolean.")
        sensor_values[slot_number] = value

    with transaction_scope():
        system_state = db.session.execute(
            select(ParkingSystemState).where(ParkingSystemState.id == 1).with_for_update()
        ).scalar_one_or_none()

        if system_state is None:
            raise ApiError("Parking gate state has not been initialized.", 503)

        system_state.last_iot_update = utcnow()

        slots = db.session.execute(
            select(ParkingSlot)
            .where(ParkingSlot.slot_number.in_(["S1", "S2", "S3"]))
            .with_for_update()
        ).scalars().all()

        for slot in slots:
            detected = sensor_values.get(slot.slot_number)
            if detected is None:
                continue

            new_sensor_status = SENSOR_OCCUPIED if detected else SENSOR_EMPTY

            if slot.status == SLOT_RESERVED and detected:
                active_booking = db.session.execute(
                    select(Booking)
                    .where(
                        Booking.slot_id == slot.id,
                        Booking.status == "ACTIVE",
                        Booking.active_slot_id == slot.id
                    )
                    .with_for_update()
                ).scalar_one_or_none()

                if active_booking is not None and active_booking.entry_time is not None:
                    slot.status = SLOT_OCCUPIED

            elif (
                slot.status == SLOT_OCCUPIED
                and not detected
                and system_state.pending_exit_slot_id is None
            ):
                # --- DEBOUNCE: only trigger exit after sustained EMPTY ---
                now = _time.time()
                first_empty = _slot_empty_since.get(slot.slot_number)

                if first_empty is None:
                    # First EMPTY reading — start the debounce timer
                    _slot_empty_since[slot.slot_number] = now
                    logger.info(
                        "DEBOUNCE START slot=%s — sensor went EMPTY, waiting %.1fs before exit",
                        slot.slot_number, SLOT_EXIT_DEBOUNCE_SECONDS,
                    )
                elif (now - first_empty) >= SLOT_EXIT_DEBOUNCE_SECONDS:
                    # Sensor has been EMPTY for the full debounce period — trigger exit
                    _slot_empty_since[slot.slot_number] = None
                    slot.status = SLOT_EXITING
                    system_state.pending_exit_slot_id = slot.id
                    system_state.movement_state = MOVEMENT_EXITING
                    logger.info(
                        "DEBOUNCE CONFIRMED slot=%s — EMPTY for %.1fs, triggering EXIT",
                        slot.slot_number, SLOT_EXIT_DEBOUNCE_SECONDS,
                    )
                # else: still within debounce window, do nothing yet

            # If sensor reads OCCUPIED again, clear any pending debounce timer
            if detected and slot.slot_number in _slot_empty_since:
                if _slot_empty_since[slot.slot_number] is not None:
                    logger.info(
                        "DEBOUNCE CANCELLED slot=%s — sensor reads OCCUPIED again (car returned)",
                        slot.slot_number,
                    )
                _slot_empty_since[slot.slot_number] = None

            slot.sensor_status = new_sensor_status

    return {
        "success": True,
        "movement_state": system_state.movement_state,
        "pending_exit_slot_id": system_state.pending_exit_slot_id,
        "slots": {
            "S1": sensor_values["S1"],
            "S2": sensor_values["S2"],
            "S3": sensor_values["S3"],
        },
    }


# ============================================================
# START EXIT SEQUENCE
# ============================================================

def start_exit_sequence() -> dict:
    with transaction_scope():
        system_state = db.session.execute(
            select(ParkingSystemState).where(ParkingSystemState.id == 1).with_for_update()
        ).scalar_one_or_none()

        if system_state is None:
            raise ApiError("Parking gate state has not been initialized.", 503)

        if system_state.movement_state not in (MOVEMENT_IDLE, MOVEMENT_EXITING):
            return {
                "started": False,
                "movement_state": system_state.movement_state,
                "pending_exit_slot_id": system_state.pending_exit_slot_id,
            }

        exiting_or_occupied_slots = db.session.execute(
            select(ParkingSlot).where(ParkingSlot.status.in_([SLOT_OCCUPIED, SLOT_EXITING])).with_for_update()
        ).scalars().all()

        if not exiting_or_occupied_slots and system_state.pending_exit_slot_id is None:
            raise ApiError("No occupied or exiting parking slot is available for exit.", 409)

        system_state.movement_state = MOVEMENT_EXITING
        system_state.last_iot_update = utcnow()

        return {
            "started": True,
            "movement_state": MOVEMENT_EXITING,
            "pending_exit_slot_id": system_state.pending_exit_slot_id,
        }


# ============================================================
# GET BOOKING STATUS
# ============================================================

def get_booking_status(booking_id: object) -> dict:
    normalized_id = _normalize_booking_id(booking_id)

    booking = db.session.execute(
        select(Booking).where(Booking.booking_id == normalized_id)
    ).scalar_one_or_none()

    if booking is None:
        return {
            "found": False,
            "booking_id": normalized_id,
            "status": None,
            "slot": None,
        }

    return {
        "found": True,
        "booking_id": booking.booking_id,
        "status": booking.status.lower(),
        "slot": booking.slot.slot_number if booking.slot else None,
    }


# ============================================================
# ADMIN DASHBOARD & MONITORING SERVICES
# ============================================================

def get_admin_dashboard_data() -> dict:
    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    slots = db.session.execute(select(ParkingSlot)).scalars().all()
    total_slots = len(slots) or 3

    available_slots = sum(1 for s in slots if s.status == SLOT_AVAILABLE)
    reserved_slots = sum(1 for s in slots if s.status == SLOT_RESERVED)
    occupied_slots = sum(1 for s in slots if s.status == SLOT_OCCUPIED)
    exiting_slots = sum(1 for s in slots if s.status == SLOT_EXITING)

    active_bookings = db.session.execute(
        select(Booking).where(Booking.status == "ACTIVE")
    ).scalars().all()

    today_bookings = db.session.execute(
        select(Booking).where(Booking.created_at >= today_start)
    ).scalars().all()

    today_exits = db.session.execute(
        select(Booking).where(Booking.status == "COMPLETED", Booking.exit_time >= today_start)
    ).scalars().all()

    system_state = db.session.get(ParkingSystemState, 1)
    sorted_slots = sorted(slots, key=lambda x: x.slot_number)

    pending_entry_booking_code = None
    if system_state and system_state.pending_entry_booking_id:
        p_booking = db.session.get(Booking, system_state.pending_entry_booking_id)
        if p_booking:
            pending_entry_booking_code = f"{p_booking.booking_id} (Authorized)"
    elif system_state and system_state.entry_vehicle_waiting:
        w_booking = db.session.execute(
            select(Booking)
            .where(Booking.status == "ACTIVE", Booking.entry_time.is_(None))
            .order_by(Booking.id.desc())
        ).scalars().first()
        if w_booking:
            pending_entry_booking_code = f"{w_booking.booking_id} (Waiting Approval)"

    pending_exit_slot_code = None
    if system_state and system_state.pending_exit_slot_id:
        p_slot = db.session.get(ParkingSlot, system_state.pending_exit_slot_id)
        if p_slot:
            pending_exit_slot_code = p_slot.slot_number
    elif system_state and system_state.exit_vehicle_waiting:
        exiting_slot = db.session.execute(
            select(ParkingSlot).where(ParkingSlot.status.in_([SLOT_EXITING, SLOT_OCCUPIED]))
        ).scalars().first()
        if exiting_slot:
            pending_exit_slot_code = f"{exiting_slot.slot_number} (At Exit Gate)"

    return {
        "total_slots": total_slots,
        "available_slots": available_slots,
        "reserved_slots": reserved_slots,
        "occupied_slots": occupied_slots,
        "exiting_slots": exiting_slots,
        "active_bookings_count": len(active_bookings),
        "active_vehicles_count": occupied_slots,
        "today_bookings_count": len(today_bookings),
        "today_completed_exits_count": len(today_exits),
        "movement_state": system_state.movement_state if system_state else "IDLE",
        "entry_vehicle_waiting": system_state.entry_vehicle_waiting if system_state else False,
        "pending_entry_booking_id": pending_entry_booking_code,
        "pending_exit_slot": pending_exit_slot_code,
        "last_iot_update": format_dt_iso(system_state.updated_at) if system_state else None,
        "slots": [
            {
                "slot": s.slot_number,
                "status": s.status.lower(),
                "sensor_status": s.sensor_status.lower(),
                "vehicle_number": next((b.vehicle_number for b in active_bookings if b.slot_id == s.id), None)
            }
            for s in sorted_slots
        ]
    }


def get_admin_bookings_data(search: str = "", status_filter: str = "all") -> list:
    query = select(Booking).order_by(Booking.created_at.desc())

    if status_filter and status_filter.lower() != "all":
        query = query.where(Booking.status == status_filter.upper())

    bookings = db.session.execute(query).scalars().all()

    results = []
    search_lower = search.lower().strip()
    for b in bookings:
        b_dict = b.as_api_dict()
        if search_lower:
            user_name = b.user.name.lower() if b.user else ""
            user_email = b.user.email.lower() if (b.user and b.user.email) else ""
            user_phone = b.user.phone if b.user else ""

            match = (
                search_lower in b.booking_id.lower() or
                search_lower in b.vehicle_number.lower() or
                search_lower in user_name or
                search_lower in user_email or
                search_lower in user_phone
            )
            if not match:
                continue
        results.append(b_dict)
    return results


def get_admin_vehicles_data() -> list:
    bookings = db.session.execute(
        select(Booking).where(Booking.status == "ACTIVE").order_by(Booking.id.desc())
    ).scalars().all()

    results = []
    for b in bookings:
        results.append({
            "booking_id": b.booking_id,
            "vehicle_number": b.vehicle_number,
            "user_name": b.user.name if b.user else "",
            "user_email": b.user.email if b.user else "",
            "user_phone": b.user.phone if b.user else "",
            "slot": b.slot.slot_number if b.slot else "",
            "entry_time": format_dt_iso(b.entry_time),
            "current_status": b.slot.status.lower() if b.slot else b.status.lower()
        })
    return results


def get_admin_statistics_data() -> dict:
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    total_bookings = db.session.execute(select(Booking)).scalars().all()
    slots = db.session.execute(select(ParkingSlot)).scalars().all()

    occupied_count = sum(1 for s in slots if s.status == SLOT_OCCUPIED)
    reserved_count = sum(1 for s in slots if s.status == SLOT_RESERVED)
    available_count = sum(1 for s in slots if s.status == SLOT_AVAILABLE)

    total_slots = len(slots) or 3
    utilization_pct = round(((occupied_count + reserved_count) / total_slots) * 100, 1)

    daily_stats = []
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        count = 0
        for b in total_bookings:
            if b.created_at:
                b_date = b.created_at.date() if hasattr(b.created_at, "date") else b.created_at
                if b_date == day_date:
                    count += 1
        daily_stats.append({
            "date": day_date.strftime("%d/%m/%Y"),
            "count": count
        })

    completed_sessions = sum(1 for b in total_bookings if b.status == "COMPLETED")

    return {
        "total_bookings_count": len(total_bookings),
        "available_count": available_count,
        "reserved_count": reserved_count,
        "occupied_count": occupied_count,
        "utilization_percentage": utilization_pct,
        "completed_sessions_count": completed_sessions,
        "daily_bookings": daily_stats
    }


def get_admin_iot_status_data() -> dict:
    state = db.session.get(ParkingSystemState, 1)
    slots = db.session.execute(select(ParkingSlot).order_by(ParkingSlot.slot_number)).scalars().all()

    gate_status = "CLOSED"
    if state and state.movement_state in (MOVEMENT_ENTERING, MOVEMENT_EXITING):
        gate_status = "OPEN"

    pending_booking = None
    if state and state.pending_entry_booking_id:
        p_booking = db.session.get(Booking, state.pending_entry_booking_id)
        if p_booking:
            pending_booking = f"{p_booking.booking_id} (Authorized)"
    elif state and state.entry_vehicle_waiting:
        w_booking = db.session.execute(
            select(Booking)
            .where(Booking.status == "ACTIVE", Booking.entry_time.is_(None))
            .order_by(Booking.id.desc())
        ).scalars().first()
        if w_booking:
            pending_booking = f"{w_booking.booking_id} (Waiting Approval)"

    pending_exit_slot = None
    if state and state.pending_exit_slot_id:
        p_slot = db.session.get(ParkingSlot, state.pending_exit_slot_id)
        if p_slot:
            pending_exit_slot = p_slot.slot_number

    return {
        "entry_sensor": "OCCUPIED" if (state and state.entry_vehicle_waiting) else "EMPTY",
        "exit_sensor": "OCCUPIED" if (state and state.exit_vehicle_waiting) else "EMPTY",
        "gate_status": gate_status,
        "movement_state": state.movement_state if state else "IDLE",
        "pending_entry_booking_id": pending_booking,
        "pending_exit_slot": pending_exit_slot,
        "last_iot_update": format_dt_iso(state.updated_at) if state else None,
        "slots_sensor_status": {
            s.slot_number: s.sensor_status for s in slots
        }
    }


def simulate_admin_sensor_trigger(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.")

    with transaction_scope():
        system_state = db.session.execute(
            select(ParkingSystemState).where(ParkingSystemState.id == 1).with_for_update()
        ).scalar_one_or_none()

        if system_state is None:
            raise ApiError("Parking system state is unavailable.", 503)

        if "vehicle_waiting" in payload and isinstance(payload["vehicle_waiting"], bool):
            system_state.entry_vehicle_waiting = payload["vehicle_waiting"]
            system_state.last_iot_update = utcnow()

        if "exit_vehicle_waiting" in payload and isinstance(payload["exit_vehicle_waiting"], bool):
            system_state.exit_vehicle_waiting = payload["exit_vehicle_waiting"]
            system_state.last_iot_update = utcnow()

        if payload.get("toggle_entry") is True:
            system_state.entry_vehicle_waiting = not system_state.entry_vehicle_waiting
            system_state.last_iot_update = utcnow()

    return {
        "success": True,
        "entry_vehicle_waiting": system_state.entry_vehicle_waiting,
        "message": f"Entry sensor state updated to {'WAITING (Vehicle Detected)' if system_state.entry_vehicle_waiting else 'CLEAR'}."
    }