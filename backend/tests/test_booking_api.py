PAYLOAD = {
    "name": "Asha Patil",
    "phone": "9876543210",
    "vehicle_number": "MH12AB1234",
    "slot": "S1",
}

IOT_HEADERS = {"X-IoT-Key": "test-iot-key"}


def test_slots_are_seeded(client):
    response = client.get("/api/slots")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "slots": [
            {"slot": "S1", "status": "available"},
            {"slot": "S2", "status": "available"},
            {"slot": "S3", "status": "available"},
        ],
    }


def test_book_then_cancel_returns_slot_to_available(client):
    created = client.post("/api/book", json=PAYLOAD)
    assert created.status_code == 201
    booking_id = created.get_json()["booking"]["booking_id"]

    slots_after_booking = client.get("/api/slots").get_json()["slots"]
    assert slots_after_booking[0]["status"] == "reserved"

    cancelled = client.post("/api/cancel", json={"booking_id": booking_id})
    assert cancelled.status_code == 200
    assert cancelled.get_json()["booking"]["status"] == "cancelled"
    assert client.get("/api/slots").get_json()["slots"][0]["status"] == "available"


def test_second_booking_for_reserved_slot_is_rejected(client):
    assert client.post("/api/book", json=PAYLOAD).status_code == 201
    second = client.post("/api/book", json={**PAYLOAD, "phone": "9123456789"})
    assert second.status_code == 409
    assert second.get_json()["message"] == "Slot S1 is no longer available."


def test_invalid_booking_payload_is_rejected(client):
    response = client.post("/api/book", json={**PAYLOAD, "vehicle_number": "bad!"})
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_iot_routes_require_the_device_key(client):
    response = client.post("/api/iot/entry", json={"vehicle_waiting": True})
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_entry_authorization_requires_sensor_then_is_consumed_once(client):
    created = client.post("/api/book", json=PAYLOAD)
    booking_id = created.get_json()["booking"]["booking_id"]

    denied = client.post("/api/enter-parking", json={"booking_id": booking_id})
    assert denied.status_code == 409
    assert "not detected" in denied.get_json()["message"]

    sensor_report = client.post(
        "/api/iot/entry",
        json={"vehicle_waiting": True},
        headers=IOT_HEADERS,
    )
    assert sensor_report.status_code == 200
    assert sensor_report.get_json()["vehicle_waiting"] is True

    authorized = client.post("/api/enter-parking", json={"booking_id": booking_id})
    assert authorized.status_code == 200
    assert authorized.get_json()["authorized"] is True

    first_poll = client.get("/api/iot/entry-status", headers=IOT_HEADERS).get_json()
    assert first_poll["success"] is True
    assert first_poll["authorized"] is True
    assert first_poll["booking_id"] == booking_id

    second_poll = client.get("/api/iot/entry-status", headers=IOT_HEADERS).get_json()
    assert second_poll["authorized"] is False
    assert second_poll["booking_id"] is None

    reused = client.post("/api/enter-parking", json={"booking_id": booking_id})
    assert reused.status_code == 409
    assert "already been used" in reused.get_json()["message"]


def test_user_registration_and_login_flow(client):
    reg = client.post("/api/auth/register", json={
        "name": "Rohan Sharma",
        "email": "rohan@example.com",
        "phone": "9823012345",
        "password": "Password123",
        "confirm_password": "Password123"
    })
    assert reg.status_code == 201
    assert reg.get_json()["success"] is True
    assert reg.get_json()["message"] == "Registration successful. Please login to continue."
    assert "token" not in reg.get_json()

    # Login
    login = client.post("/api/auth/login", json={
        "email": "rohan@example.com",
        "password": "Password123"
    })
    assert login.status_code == 200
    assert login.get_json()["user"]["email"] == "rohan@example.com"
    token = login.get_json()["token"]
    assert token is not None

    # Profile check with Bearer token
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.get_json()["user"]["name"] == "Rohan Sharma"


def test_forgot_password_and_reset_flow(client):
    client.post("/api/auth/register", json={
        "name": "Reset User",
        "email": "reset@example.com",
        "phone": "9998887776",
        "password": "OldPassword123",
        "confirm_password": "OldPassword123"
    })

    forgot = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert forgot.status_code == 200
    assert forgot.get_json()["message"] == "If an account exists for this email, password reset instructions have been sent."
    token = forgot.get_json().get("reset_token")
    assert token is not None

    old_login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "OldPassword123"})
    assert old_login.status_code == 200

    reset = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "NewPassword123",
        "confirm_password": "NewPassword123"
    })
    assert reset.status_code == 200
    assert reset.get_json()["success"] is True

    failed_login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "OldPassword123"})
    assert failed_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "NewPassword123"})
    assert new_login.status_code == 200


def test_admin_authentication_and_dashboard_endpoints(client):
    # Public user cannot access admin APIs
    denied = client.get("/api/admin/dashboard")
    assert denied.status_code == 401

    # Admin Login
    admin_login = client.post("/api/admin/login", json={
        "email": "admin@parkease.com",
        "password": "Admin123!"
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["token"]

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Dashboard data
    dash = client.get("/api/admin/dashboard", headers=admin_headers)
    assert dash.status_code == 200
    assert dash.get_json()["total_slots"] == 3

    # Bookings list
    bookings = client.get("/api/admin/bookings", headers=admin_headers)
    assert bookings.status_code == 200

    # Statistics
    stats = client.get("/api/admin/statistics", headers=admin_headers)
    assert stats.status_code == 200

    # IoT Status
    iot = client.get("/api/admin/iot-status", headers=admin_headers)
    assert iot.status_code == 200
    assert "slots_sensor_status" in iot.get_json()


def test_admin_sensor_simulation_flow(client):
    admin_login = client.post("/api/admin/login", json={
        "email": "admin@parkease.com",
        "password": "Admin123!"
    })
    admin_token = admin_login.get_json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Simulate vehicle waiting
    sim = client.post("/api/admin/simulate-sensor", json={"vehicle_waiting": True}, headers=admin_headers)
    assert sim.status_code == 200
    assert sim.get_json()["entry_vehicle_waiting"] is True

    # Check public entry status
    status = client.get("/api/entry-status")
    assert status.status_code == 200
    assert status.get_json()["vehicle_waiting"] is True

