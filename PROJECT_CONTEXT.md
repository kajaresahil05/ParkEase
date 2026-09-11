# ParkEase — Project Context for Codex

## 1. Project Overview

ParkEase is a college major project for a Smart Parking System.

The system combines:
- A web-based parking dashboard
- Flask backend APIs
- MySQL database
- ESP32 IoT controller
- IR sensors for vehicle/slot detection
- Servo motor for the parking gate

The goal is to allow users to view parking availability, reserve a slot, arrive at the parking entrance, verify their active booking from their phone, automatically authorize the ESP32 gate, and detect parking/exit using IoT sensors.

This document describes the current agreed architecture and behavior. Read it before modifying the project.

---

## 2. Current Architecture

```text
                    ┌──────────────────────┐
                    │       User Phone     │
                    │   ParkEase Website   │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │    Flask Backend     │
                    │      Railway         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     MySQL Database   │
                    │       Railway        │
                    └──────────────────────┘
                               ▲
                               │ Wi-Fi / HTTP
                    ┌──────────┴───────────┐
                    │        ESP32         │
                    │  IR Sensors + Servo  │
                    └──────────────────────┘
```

Hosting plan:
- Frontend → Vercel
- Flask backend → Railway
- MySQL → Railway

IMPORTANT:
- ESP32 must NOT connect directly to MySQL.
- ESP32 communicates with Flask APIs.
- MySQL is the source of truth for bookings and parking state.
- Frontend must not be trusted for booking concurrency or authorization decisions.

---

## 3. Existing Frontend

The current frontend consists of:

```text
index.html
style.css
script.js
```

The existing UI should be preserved.

Do NOT redesign the website unnecessarily.

Current frontend features:
- Responsive layout
- Light/dark theme
- Parking slot cards
- Available/reserved/occupied status
- Booking modal
- My Booking section
- Vehicle number field
- Booking ID display
- Enter Parking section
- Entry status UI

The frontend was initially localStorage-based and is now API-ready.

Current local prototype behavior is intentionally retained until the Flask backend is implemented.

---

## 4. Parking Slots

There are currently 3 parking slots:

```text
S1
S2
S3
```

Public slot states:

```text
AVAILABLE
RESERVED
OCCUPIED
```

Internal IoT state may also include:

```text
EXITING
```

Meaning:

- AVAILABLE → slot can be booked
- RESERVED → active booking exists but vehicle has not parked
- OCCUPIED → vehicle is detected in the slot
- EXITING → vehicle has left the slot but has not yet completely exited the parking area

Public UI colors:
- Green → AVAILABLE
- Yellow → RESERVED
- Red → OCCUPIED

EXITING can be represented internally and does not necessarily need to be shown as a public booking state.

---

## 5. ESP32 Hardware

Current board:

- 30-pin ESP32 development board
- ESP32-WROOM-32 style board
- Exact board variant should not be assumed beyond what is confirmed by the hardware.

Current GPIO assignments:

```text
Entry IR OUT → GPIO18
Exit IR OUT  → GPIO19

Slot 1 IR OUT → GPIO21
Slot 2 IR OUT → GPIO22
Slot 3 IR OUT → GPIO23

Servo signal → GPIO25
```

IR sensors:
- Typical modules are active LOW.
- Sensor output must be ESP32-safe.
- Do not feed a 5V sensor output directly into ESP32 GPIO.
- Use 3.3V logic where appropriate.

Servo:
- Signal → GPIO25
- Servo power → external 5V
- Servo GND → external GND
- ESP32 GND and servo power GND must be common
- Do NOT power the servo from ESP32 3.3V

Basic hardware testing has already been completed successfully:
- Servo movement works.
- IR sensors work.

---

## 6. Physical Gate Layout

The physical arrangement is:

```text
Road / Incoming Vehicle
        ↓
   Entry IR
        ↓
   Servo Gate
        ↓
    Exit IR
        ↓
 Parking Area
   S1 / S2 / S3
```

Entry IR is BEFORE the gate.

Entry IR does NOT automatically open the gate.

Its purpose is to detect that a vehicle is waiting at the entrance.

The user must then press:

```text
ENTER PARKING
```

on their phone.

The backend verifies the user's active booking.

If valid, the ESP32 is authorized to open the servo gate.

---

## 7. Complete Entry Flow

The intended entry flow is:

```text
1. User books S1/S2/S3.
        ↓
2. Booking becomes RESERVED.
        ↓
3. User drives to parking entrance.
        ↓
4. Entry IR detects vehicle waiting.
        ↓
5. ESP32 reports vehicle waiting to Flask.
        ↓
6. User's phone shows vehicle detected.
        ↓
7. User taps ENTER PARKING.
        ↓
8. Frontend sends booking ID to Flask.
        ↓
9. Flask verifies active booking.
        ↓
10. Flask authorizes entry.
        ↓
11. ESP32 receives authorization.
        ↓
12. Servo opens.
        ↓
13. Vehicle passes through gate.
        ↓
14. Exit IR detects vehicle after gate.
        ↓
15. Servo closes.
        ↓
16. Vehicle reaches its reserved slot.
        ↓
17. Slot IR detects vehicle.
        ↓
18. Slot becomes OCCUPIED.
```

Important:
- Entry IR detection alone must NEVER authorize entry.
- A valid active booking is required.
- The backend must make the authorization decision.
- ESP32 only acts on backend authorization.

---

## 8. Exit Flow

The intended exit flow is:

```text
1. Vehicle leaves its occupied slot.
        ↓
2. Slot IR changes from occupied to empty.
        ↓
3. During an active exit sequence,
   that slot becomes EXITING.
        ↓
4. Vehicle reaches Exit IR.
        ↓
5. ESP32 opens gate for exit.
        ↓
6. Vehicle passes the gate.
        ↓
7. Entry IR detects the vehicle after the gate.
        ↓
8. Vehicle has completed exit.
        ↓
9. Servo closes.
        ↓
10. EXITING slot becomes AVAILABLE.
```

Important:
- A slot must NOT immediately become AVAILABLE just because its slot sensor becomes empty.
- This prevents a false available state while the vehicle is still leaving.
- The slot becomes AVAILABLE only after the exit sequence is confirmed.

---

## 9. Vehicle Direction Logic

With the current two gate sensors:

```text
Entry → Exit = ENTRY

Exit → Entry = EXIT
```

Entry sequence:
- Entry IR first
- Exit IR second

Exit sequence:
- Exit IR first
- Entry IR second

The ESP32/backend should use this sequence to determine direction.

There are only five sensors, so the prototype cannot always know with absolute certainty which occupied slot a departing vehicle came from if multiple vehicles are present.

For the college prototype, the agreed approach is:
- During an active exit sequence, identify the occupied slot that changes from occupied to empty.
- Mark it EXITING.
- Confirm complete exit using Entry IR.
- Then make that slot AVAILABLE.

This limitation should be documented rather than hidden.

---

## 10. Booking System

The booking form requires:

```text
Name
Mobile Number
Vehicle Number
Selected Slot
```

A booking should generate a Booking ID such as:

```text
PE-123456
```

The frontend currently displays:
- Booking ID
- Vehicle number
- Slot

The booking is considered active until:
- cancelled,
- completed,
- or otherwise closed by backend logic.

---

## 11. Critical Concurrency Requirement

Multiple users must NOT be able to reserve the same slot simultaneously.

This MUST be enforced by the backend/database.

Do NOT rely only on:
- frontend button state,
- localStorage,
- JavaScript checks,
- cached slot availability.

Example race condition:

```text
User A sees S1 AVAILABLE
User B sees S1 AVAILABLE

User A clicks BOOK NOW
User B clicks BOOK NOW
```

Only one user may successfully reserve S1.

Recommended backend approach:
- Start a database transaction.
- Lock/recheck the slot row.
- Verify it is still AVAILABLE.
- Create the booking.
- Change slot to RESERVED.
- Commit transaction.
- If another request already reserved it, return an error such as:
  "Slot S1 is no longer available."

A database-level uniqueness rule for active bookings per slot should also be considered.

MySQL is the source of truth.

---

## 12. Recommended Database Structure

Initial tables:

### users

```text
id
name
email
phone
created_at
```

### parking_slots

```text
id
slot_number
status
sensor_status
updated_at
```

Example:

```text
1 | S1 | AVAILABLE | EMPTY
2 | S2 | RESERVED  | EMPTY
3 | S3 | OCCUPIED  | OCCUPIED
```

### bookings

Suggested fields:

```text
id
booking_id
user_id
slot_id
vehicle_number
booking_time
status
entry_authorized
entry_time
exit_time
created_at
updated_at
```

Booking statuses may include:

```text
ACTIVE
CANCELLED
COMPLETED
```

Slot status is separate from booking status.

Do not unnecessarily duplicate state in ways that can become inconsistent.

---

## 13. Backend API Plan

Recommended endpoints:

### GET /api/slots

Returns current slot states.

Example response:

```json
{
  "success": true,
  "slots": [
    {
      "slot": "S1",
      "status": "available"
    },
    {
      "slot": "S2",
      "status": "reserved"
    },
    {
      "slot": "S3",
      "status": "occupied"
    }
  ]
}
```

---

### POST /api/book

Creates a booking.

Request:

```json
{
  "name": "User Name",
  "phone": "9876543210",
  "vehicle_number": "MH12AB1234",
  "slot": "S1"
}
```

Backend must:
1. Validate data.
2. Verify slot exists.
3. Recheck slot availability inside a transaction.
4. Prevent concurrent double booking.
5. Create booking.
6. Set slot to RESERVED.
7. Return booking details.

---

### POST /api/cancel

Cancels an active booking.

Request should contain the booking identifier.

Backend should:
1. Verify booking exists and is active.
2. Cancel booking.
3. Make slot AVAILABLE if appropriate.
4. Commit transaction.

---

### POST /api/enter-parking

Frontend sends:

```json
{
  "booking_id": "PE-123456"
}
```

Backend should:
1. Find booking.
2. Verify it is active.
3. Verify associated slot is RESERVED.
4. Verify entry has not already been used.
5. Verify any required vehicle/entry conditions.
6. Authorize entry.
7. Make authorization available to ESP32.
8. Return success/failure.

Example success:

```json
{
  "success": true,
  "authorized": true,
  "message": "Entry authorized."
}
```

Example failure:

```json
{
  "success": false,
  "authorized": false,
  "message": "Booking is invalid or inactive."
}
```

---

### POST /api/iot/slots

ESP32 reports slot sensor states.

Example:

```json
{
  "slots": {
    "S1": "occupied",
    "S2": "empty",
    "S3": "empty"
  }
}
```

Backend updates the appropriate slot state according to the state machine.

---

### POST /api/iot/entry

ESP32 reports entry sensor state.

Possible payload:

```json
{
  "vehicle_waiting": true
}
```

---

### POST /api/iot/exit

ESP32 reports exit sensor state.

Possible payload:

```json
{
  "vehicle_detected": true
}
```

---

### GET /api/iot/entry-status

ESP32 can poll for a pending authorization.

Possible response:

```json
{
  "authorized": true,
  "booking_id": "PE-123456"
}
```

After the authorization is consumed, it must not remain reusable.

---

## 14. ESP32 ↔ Flask Principle

ESP32 should not know how to query MySQL.

Correct:

```text
ESP32
  ↓ HTTP
Flask API
  ↓ SQL
MySQL
```

Incorrect:

```text
ESP32
  ↓
MySQL
```

The Flask backend controls authorization and database state.

---

## 15. Frontend Entry State

The frontend should show:

### No booking

```text
No active reservation
```

### Booking exists, no vehicle at entrance

```text
Ready for entry

Reach the entry sensor, then tap Enter Parking.
```

Enter Parking button should be disabled.

### Entry sensor detects vehicle

```text
Vehicle detected

Your vehicle is waiting at the entrance.
Tap Enter Parking to verify.
```

Button enabled.

### Backend verification

```text
Verifying...
```

### Successful authorization

```text
Entry authorized

Your booking has been verified.
The smart gate can open.
```

Button disabled after successful authorization.

### Failed verification

```text
Entry denied

Booking could not be verified.
```

The frontend should not pretend entry succeeded when the backend rejects it.

---

## 16. Current Frontend Prototype

The frontend currently has a local prototype mode.

There is an API configuration concept:

```javascript
const API_BASE_URL = "";
```

When the backend is deployed, it should become something like:

```javascript
const API_BASE_URL =
    "https://YOUR-RAILWAY-BACKEND.up.railway.app";
```

Do not hard-code a fake Railway URL.

When API_BASE_URL is empty, the frontend can remain usable for local UI testing.

When API_BASE_URL is configured, frontend booking and entry operations should use Flask.

---

## 17. Current Frontend Requirement

Preserve the existing design.

Do not:
- replace the entire UI,
- remove dark mode,
- remove responsive behavior,
- create an unrelated design,
- rewrite working components unnecessarily.

Modify only what is required for backend integration.

---

## 18. Security / Validation Principles

Backend must validate all important input.

Do not trust:
- slot status sent by frontend,
- vehicle number sent by frontend,
- booking status sent by frontend,
- authorization status sent by frontend.

The backend/database is authoritative.

At minimum:
- Validate vehicle number format.
- Validate phone number.
- Validate slot identifier.
- Validate booking ID.
- Prevent unauthorized entry.
- Prevent booking the same slot twice.
- Prevent reusing an entry authorization.
- Use parameterized SQL / ORM queries.
- Keep database credentials in environment variables.
- Do not commit secrets to Git.

For a college prototype, full authentication is not required yet unless explicitly added later.

---

## 19. Current Authentication Assumption

There is currently NO full login/authentication system.

The prototype can identify a reservation using the active booking information on the same phone/browser.

Do not assume a user's identity can automatically be known across devices.

Proper authentication can be added later.

---

## 20. Development Strategy

Build incrementally.

Recommended order:

### Phase 1
Create Flask project.

### Phase 2
Connect Flask to MySQL.

### Phase 3
Create database schema/tables.

### Phase 4
Implement:

```text
GET /api/slots
POST /api/book
POST /api/cancel
```

### Phase 5
Connect frontend to these APIs.

### Phase 6
Implement:

```text
POST /api/enter-parking
GET /api/iot/entry-status
```

### Phase 7
Implement ESP32 communication.

### Phase 8
Implement slot sensor state machine.

### Phase 9
Implement entry/exit gate state machine.

### Phase 10
Test complete physical flow.

Do not implement everything in one giant untested change.

---

## 21. Current Status

Already completed:
- Frontend UI exists.
- Existing frontend has been updated for vehicle number and entry verification UI.
- ESP32 hardware has been tested.
- IR sensors work.
- Servo works.
- GPIO mapping has been established.
- Entry/exit direction concept has been established.
- Slot EXITING concept has been established.
- Backend + MySQL architecture has been selected.
- Railway is the planned backend/database hosting platform.
- Vercel is the planned frontend hosting platform.
- QR scanner hardware has been intentionally removed from the design due to cost.
- Software-based booking verification from the user's phone is the chosen approach.

Not yet completed:
- Flask backend
- MySQL database
- Production API integration
- ESP32 HTTP communication
- Complete booking concurrency implementation
- Complete entry authorization communication
- Complete physical end-to-end test

---

## 22. Important Instructions for Codex

Before changing code:
1. Read this file.
2. Inspect the existing project files.
3. Understand existing functions before replacing them.
4. Preserve the existing frontend design.
5. Avoid unnecessary rewrites.
6. Build and test incrementally.
7. Clearly report which files were changed.
8. Do not invent hardware pins.
9. Do not connect ESP32 directly to MySQL.
10. Do not trust frontend slot availability for booking concurrency.
11. Do not authorize entry merely because Entry IR detected a vehicle.
12. Backend must verify an active booking before gate authorization.
13. Do not mark an exiting slot AVAILABLE prematurely.
14. Keep secrets in environment variables.
15. If a requirement is ambiguous, inspect the existing code and this context first; ask only when necessary.

---

## 23. Immediate Next Task

The immediate task is:

**Build the ParkEase Flask + MySQL backend while preserving compatibility with the existing frontend.**

Start with:
- Flask application structure
- environment configuration
- MySQL connection
- SQLAlchemy or another clean database layer
- models/schema
- `/api/slots`
- `/api/book`
- `/api/cancel`
- concurrency-safe slot reservation

After that, integrate the existing frontend.

Do NOT start with ESP32 communication until the basic backend/database booking flow works.
