import hmac
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from .auth import get_current_user, require_admin, require_user
from .extensions import db
from .models import Booking, ParkingSlot, ParkingSystemState
from .services import (
    ApiError,
    authorize_entry,
    cancel_booking,
    complete_entry_sequence,
    consume_entry_authorization,
    create_booking,
    get_admin_bookings_data,
    get_admin_dashboard_data,
    get_admin_iot_status_data,
    get_admin_statistics_data,
    get_admin_vehicles_data,
    get_booking_status,
    login_admin,
    login_user,
    register_user,
    report_entry_sensor,
    report_slot_sensors,
    request_password_reset,
    reset_password,
    simulate_admin_sensor_trigger,
    start_exit_sequence,
)

api = Blueprint("api", __name__, url_prefix="/api")


# ============================================================
# IoT API KEY AUTHENTICATION
# ============================================================

def require_iot_key(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        expected_key = current_app.config["IOT_API_KEY"]
        received_key = request.headers.get("X-IoT-Key", "")

        if not expected_key:
            raise ApiError("IoT API key has not been configured.", 503)

        if not hmac.compare_digest(received_key, expected_key):
            raise ApiError("IoT device is not authorized.", 401)

        return view(*args, **kwargs)

    return wrapped_view


# ============================================================
# USER AUTHENTICATION API
# ============================================================

@api.post("/auth/register")
def auth_register():
    user = register_user(request.get_json(silent=True))
    return jsonify(
        success=True,
        message="Registration successful. Please login to continue.",
        user=user.as_api_dict()
    ), 201


@api.post("/auth/login")
def auth_login():
    user, token = login_user(request.get_json(silent=True))
    return jsonify(
        success=True,
        message="Login successful.",
        token=token,
        user=user.as_api_dict()
    )


@api.post("/auth/forgot-password")
def auth_forgot_password():
    data = request_password_reset(request.get_json(silent=True))
    return jsonify(data)


@api.post("/auth/reset-password")
def auth_reset_password():
    reset_password(request.get_json(silent=True))
    return jsonify(
        success=True,
        message="Password reset successful. Please login with your new password."
    )


@api.post("/auth/logout")
def auth_logout():
    return jsonify(
        success=True,
        message="Logged out successfully."
    )


@api.get("/auth/me")
@require_user
def auth_me():
    user = request.current_user
    active_booking = db.session.execute(
        select(Booking)
        .where(Booking.user_id == user.id, Booking.status == "ACTIVE")
    ).scalar_one_or_none()

    return jsonify(
        success=True,
        user=user.as_api_dict(),
        active_booking=active_booking.as_api_dict() if active_booking else None
    )


@api.get("/user/bookings")
@require_user
def user_bookings():
    user = request.current_user
    bookings = db.session.execute(
        select(Booking)
        .where(Booking.user_id == user.id)
        .order_by(Booking.created_at.desc())
    ).scalars().all()

    return jsonify(
        success=True,
        bookings=[b.as_api_dict() for b in bookings]
    )


# ============================================================
# ADMIN AUTHENTICATION API
# ============================================================

@api.post("/admin/login")
def admin_login_route():
    admin_dict, token = login_admin(request.get_json(silent=True))
    return jsonify(
        success=True,
        message="Admin authentication successful.",
        token=token,
        admin=admin_dict
    )


@api.post("/admin/logout")
def admin_logout_route():
    return jsonify(
        success=True,
        message="Admin logged out successfully."
    )


# ============================================================
# ADMIN DASHBOARD API
# ============================================================

@api.get("/admin/dashboard")
@require_admin
def admin_dashboard_route():
    data = get_admin_dashboard_data()
    return jsonify(success=True, **data)


@api.get("/admin/bookings")
@require_admin
def admin_bookings_route():
    search = request.args.get("search", "")
    status_filter = request.args.get("status", "all")
    bookings = get_admin_bookings_data(search=search, status_filter=status_filter)
    return jsonify(success=True, bookings=bookings, count=len(bookings))


@api.get("/admin/vehicles")
@require_admin
def admin_vehicles_route():
    vehicles = get_admin_vehicles_data()
    return jsonify(success=True, vehicles=vehicles, count=len(vehicles))


@api.get("/admin/statistics")
@require_admin
def admin_statistics_route():
    stats = get_admin_statistics_data()
    return jsonify(success=True, **stats)


@api.get("/admin/iot-status")
@require_admin
def admin_iot_status_route():
    status = get_admin_iot_status_data()
    return jsonify(success=True, **status)


@api.post("/admin/simulate-sensor")
@require_admin
def admin_simulate_sensor_route():
    res = simulate_admin_sensor_trigger(request.get_json(silent=True) or {})
    return jsonify(res)



# ============================================================
# PARKING SLOT STATUS
# ============================================================

@api.get("/slots")
def get_slots():
    slots = (
        db.session
        .execute(select(ParkingSlot).order_by(ParkingSlot.slot_number))
        .scalars()
    )

    return jsonify(
        success=True,
        slots=[slot.as_api_dict() for slot in slots]
    )


# ============================================================
# CREATE BOOKING
# ============================================================

@api.post("/book")
def book_slot():
    user = get_current_user()
    booking = create_booking(request.get_json(silent=True), current_user=user)

    return jsonify(
        success=True,
        message="Slot booked successfully.",
        booking=booking.as_api_dict()
    ), 201


# ============================================================
# CANCEL BOOKING
# ============================================================

@api.post("/cancel")
def cancel_slot_booking():
    user = get_current_user()
    payload = request.get_json(silent=True)

    booking_id = payload.get("booking_id") if isinstance(payload, dict) else None
    booking = cancel_booking(booking_id, current_user=user)

    return jsonify(
        success=True,
        message="Booking cancelled successfully.",
        booking=booking.as_api_dict()
    )


# ============================================================
# ENTER PARKING
# ============================================================

@api.post("/enter-parking")
def enter_parking():
    user = get_current_user()
    payload = request.get_json(silent=True)

    booking_id = payload.get("booking_id") if isinstance(payload, dict) else None
    booking = authorize_entry(booking_id, current_user=user)

    return jsonify(
        success=True,
        authorized=True,
        message="Entry authorized.",
        booking=booking.as_api_dict()
    )


# ============================================================
# ESP32 → FLASK: ENTRY IR SENSOR
# ============================================================

@api.post("/iot/entry")
@require_iot_key
def report_entry():
    payload = request.get_json(silent=True)
    vehicle_waiting = report_entry_sensor(payload)

    return jsonify(
        success=True,
        vehicle_waiting=vehicle_waiting
    )


# ============================================================
# ESP32 → FLASK: ENTRY AUTHORIZATION POLLING
# ============================================================

@api.get("/iot/entry-status")
@require_iot_key
def entry_status():
    return jsonify(
        success=True,
        **consume_entry_authorization()
    )


# ============================================================
# ESP32 → FLASK: ENTRY CROSSING COMPLETION
# ============================================================

@api.post("/iot/entry-crossed")
@require_iot_key
def entry_crossed():
    result = complete_entry_sequence()
    return jsonify(
        success=True,
        **result
    )


# ============================================================
# ESP32 → FLASK: SLOT SENSOR REPORT
# ============================================================

@api.post("/iot/slots")
@require_iot_key
def report_slots():
    payload = request.get_json(silent=True)
    result = report_slot_sensors(payload)
    return jsonify(result)


# ============================================================
# ESP32 → FLASK: EXIT SENSOR / EXIT SEQUENCE
# ============================================================

@api.post("/iot/exit")
@require_iot_key
def report_exit():
    result = start_exit_sequence()
    return jsonify(
        success=True,
        **result
    )


# ============================================================
# FRONTEND → FLASK: PUBLIC ENTRY SENSOR STATUS
# ============================================================

@api.get("/entry-status")
def public_entry_status():
    state = db.session.get(ParkingSystemState, 1)

    if state is None:
        return jsonify(
            success=False,
            vehicle_waiting=False,
            message="Parking system state is unavailable."
        ), 500

    return jsonify(
        success=True,
        vehicle_waiting=bool(state.entry_vehicle_waiting)
    )


# ============================================================
# BOOKING STATUS (FRONTEND POLLING)
# ============================================================

@api.get("/booking-status")
def booking_status():
    booking_id = request.args.get("booking_id")

    if not booking_id:
        raise ApiError("booking_id query parameter is required.")

    result = get_booking_status(booking_id)

    return jsonify(
        success=True,
        **result
    )


# ============================================================
# API ERROR HANDLER
# ============================================================

@api.errorhandler(ApiError)
def handle_api_error(error: ApiError):
    return jsonify(
        success=False,
        message=error.message
    ), error.status_code
