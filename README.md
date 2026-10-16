# ParkEase 🚗🅿️
### *Next-Gen IoT-Enabled Smart Parking & Gate Automation Platform*

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-black.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32%20WROOM--32-red.svg?logo=espressif&logoColor=white)](https://www.espressif.com/)
[![Database](https://img.shields.io/badge/Database-MySQL%20%7C%20PostgreSQL-4479A1.svg?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![Frontend](https://img.shields.io/badge/Frontend-HTML5%20%7C%20CSS3%20%7C%20JS-E34F26.svg?logo=html5&logoColor=white)](https://developer.mozilla.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Project Link: https://parkease-frontend-sand.vercel.app/

---

## 📌 Executive Summary

**ParkEase** is an end-to-end intelligent parking and access control management ecosystem designed to eliminate parking congestion, optimize bay occupancy, and automate barrier gate interactions without requiring high-cost RFID tags or automatic number-plate recognition (ANPR) systems.

The solution seamlessly connects:
1. **Driver Web Application**: Instant slot discovery, real-time availability indicator, concurrent-safe reservation, and one-tap entrance barrier activation.
2. **Administrative Operations Portal**: Live telemetry dashboard, slot sensor visualizer, booking audit records, vehicle registry, and interactive IoT hardware sensor simulator.
3. **Flask Microservice Backend**: Concurrency-safe RESTful API implementing transactional row-level slot locking, state machines, and authentication.
4. **ESP32 Edge Microcontroller**: Real-time sensor array polling (FC-51 IR sensors) and PWM servo-actuated gate barrier controller.

---

## 🏗️ System Architecture

```
                                ┌─────────────────────────────────────────┐
                                │          User / Admin Browsers          │
                                │  Public Web App & Admin Dashboard (JS)  │
                                └────────────────────┬────────────────────┘
                                                     │ HTTPS (REST API / JWT)
                                                     ▼
                                ┌─────────────────────────────────────────┐
                                │           Flask RESTful API             │
                                │     State Engine & Concurrency Core     │
                                └─────────────┬───────────────────────────┘
                                              │ SQLAlchemy ORM
                                              ▼
                                ┌─────────────────────────────────────────┐
                                │         Relational Database             │
                                │         (MySQL / PostgreSQL)            │
                                └─────────────────────────────────────────┘
                                                     ▲
                                                     │ Wi-Fi (HTTP + X-IoT-Key)
                                                     ▼
                                ┌─────────────────────────────────────────┐
                                │           ESP32 Microcontroller         │
                                │  (5x IR Sensors + PWM Servo Gate Motor) │
                                └─────────────────────────────────────────┘
```

> **Security Guardrail**: The ESP32 and client browsers never communicate directly with the database. The Flask backend is the sole source of truth for slot states, authorization rules, and atomic booking transactions.

---

## 🚀 Key Features

### 👤 Driver Web Application
- **Live Slot Telemetry**: Visually distinct statuses for each parking bay:
  - 🟢 **Available**: Ready for reservation.
  - 🟡 **Reserved**: Booked by a user whose vehicle is inbound.
  - 🔴 **Occupied**: Physically detected by bay IR sensors.
- **Concurrency-Safe Reservation**: Prevents race conditions with database row locking (`SELECT ... FOR UPDATE`).
- **Presence-Verified Entry**: Users cannot open the barrier remotely; the gate can only be requested when the **Entry IR sensor** physically detects a vehicle waiting at the gate.
- **Self-Service Portal**: Instant cancellation, active booking retrieval, and vehicle number verification.

### 🛡️ Admin Operations Portal
- **Real-Time IoT Overview**: Live indicator of entry sensor, exit sensor, barrier servo status, and active movement sequences.
- **Occupancy & Revenue Analytics**: Track slot utilization rates, active visitors, and peak turnover hours.
- **Hardware Simulation Console**: Test the complete entry and exit state machine directly from the web interface without physical hardware connected.
- **Security & Authorization**: Role-based access control with secure bcrypt password hashing and tokenized sessions.

### ⚙️ Backend & State Engine
- **Transactional Integrity**: Dual-layer collision prevention via database unique constraints on `active_slot_id` plus transactional lock acquire.
- **Directional State Machine**: Distinguishes incoming vs. outgoing traffic using sequential detection (`Entry IR -> Exit IR` vs `Exit IR -> Entry IR`).
- **Zero-Ghost Bay Protection**: When a vehicle leaves its bay, the slot transitions to an internal `EXITING` state and only returns to `AVAILABLE` once the barrier exit sequence is validated.

### 🔌 ESP32 Edge Controller
- **Low-Latency Polling**: Synchronizes IR inputs and polls one-time authorization tokens via JSON HTTP payloads.
- **Failsafe Gate Controller**: Automatic 10-second servo timeout ensures the barrier closes safely even if an exit sensor is missed.
- **API Key Guard**: All hardware endpoints require cryptographic constant-time header verification (`X-IoT-Key`).

---

## 🚦 Physical Gate Layout & Sequence

```
                Incoming Vehicle
                       ↓
         [ Entry IR Sensor (GPIO 18) ]      ── (Detects waiting vehicle)
                       ↓
         [ Servo Gate Barrier (GPIO 25) ]   ── (Opens upon app authorization)
                       ↓
         [ Exit IR Sensor (GPIO 19) ]       ── (Confirms crossing & triggers gate close)
                       ↓
               Parking Bay Area
         [ Slot 1 (GPIO 21) | Slot 2 (GPIO 22) | Slot 3 (GPIO 23) ]
```

### Complete End-to-End Entry Flow
1. **Reserve**: Driver reserves an available slot (e.g., `S1`) via the web app; status becomes `RESERVED`.
2. **Arrival**: Driver reaches the gate. The **Entry IR** detects the car and signals Flask (`entry_vehicle_waiting = True`).
3. **Authorization**: Driver taps **"Enter Parking"** on their phone. Flask verifies the active booking and flags an authorization token.
4. **Actuation**: The ESP32 polls `/api/iot/entry-status`, receives approval, and swings the servo open (90°).
5. **Clearance**: The vehicle passes through, tripping the **Exit IR**. The ESP32 immediately commands the servo to 0° (closed) and notifies Flask (`/api/iot/entry-crossed`).
6. **Park**: Vehicle pulls into `S1`. The **Slot 1 IR** detects obstacle; slot status switches to `OCCUPIED`.

---

## ⚡ Hardware Pinout & Wiring

| Component | ESP32 Pin | Logic Level | Notes |
| :--- | :--- | :--- | :--- |
| **Entry IR Sensor (OUT)** | `GPIO 18` | 3.3V Logic | Active LOW (FC-51 / obstacle sensor) |
| **Exit IR Sensor (OUT)** | `GPIO 19` | 3.3V Logic | Active LOW (FC-51 / obstacle sensor) |
| **Slot 1 IR Sensor (OUT)** | `GPIO 21` | 3.3V Logic | Monitors bay S1 |
| **Slot 2 IR Sensor (OUT)** | `GPIO 22` | 3.3V Logic | Monitors bay S2 |
| **Slot 3 IR Sensor (OUT)** | `GPIO 23` | 3.3V Logic | Monitors bay S3 |
| **Servo Motor Signal (PWM)** | `GPIO 25` | 3.3V PWM | SG90 or MG995 / MG996R |

> [!CAUTION]
> **Power Supply Advisory**:
> - Never power the servo motor directly from the ESP32 `3.3V` or `VIN` pins. Servos create high inductive spikes that can cause brownouts and destroy the microcontroller.
> - Use an independent **5V / 2A external DC power source** for the servo.
> - **Always tie the external power GND and the ESP32 GND together (Common Ground).**

---

## 📁 Repository Structure

```
ParkEase/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Flask factory, extensions, and CLI commands
│   │   ├── auth.py              # JWT token generation, verification, and decorators
│   │   ├── config.py            # Environment-specific configuration loader
│   │   ├── extensions.py        # SQLAlchemy instance
│   │   ├── models.py            # Database entities: User, Slot, Booking, History, State
│   │   ├── routes.py            # User, Admin, and IoT endpoint routes
│   │   └── services.py          # Core business rules, concurrency locks, state engine
│   ├── tests/
│   │   ├── conftest.py          # Pytest SQLite fixtures & test client setup
│   │   └── test_booking_api.py  # Unit & concurrency test suite
│   ├── .env.example             # Template for backend environment variables
│   ├── build.sh                 # Deployment script
│   ├── requirements.txt         # Python dependencies (Flask, SQLAlchemy, PyMySQL, etc.)
│   └── run.py                   # Application entrypoint
├── esp32/
│   ├── ParkEaseEntryClient/
│   │   └── ParkEaseEntryClient.ino # Arduino/C++ firmware for ESP32
│   ├── secrets.h.example        # Wi-Fi credentials & API key header template
│   └── README.md                # Firmware compilation and flashing guide
├── frontend/
│   ├── index.html               # Public driver booking and entry portal
│   ├── style.css                # Responsive public UI styles (Light/Dark mode)
│   ├── script.js                # Public frontend state manager & API client
│   ├── admin.html               # Admin telemetry and control console
│   ├── admin.css                # Admin portal styling and layout
│   ├── admin.js                 # Admin dashboard logic, charts, and simulation
│   └── vercel.json              # Static deployment configuration
├── render.yaml                  # Render.com Blueprint (Web Service + PostgreSQL)
├── PROJECT_CONTEXT.md           # Engineering specifications & historical context
└── README.md                    # Project documentation
```

---

## 🛠️ Getting Started

### 1. Prerequisites
- **Python 3.11+**
- **Node.js / Live Server** (optional, for frontend local serving)
- **MySQL 8.0+** or **PostgreSQL 14+**
- **Arduino IDE** (with ESP32 board definitions installed)

---

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Edit `.env` to configure your database and security keys:
```ini
FLASK_ENV=development
SECRET_KEY=your-secure-random-secret-key
IOT_API_KEY=your-hardware-shared-api-key
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500

# For MySQL:
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=parkease
MYSQL_USER=root
MYSQL_PASSWORD=your_password

# Or full database connection string:
# DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/parkease
```

Initialize database tables and default slots:
```bash
flask --app run.py init-db
```

Start the Flask development server:
```bash
flask --app run.py run --host=0.0.0.0 --port=5000 --debug
```

Run test suite:
```bash
pytest
```

---

### 3. Frontend Setup

The frontend is built with vanilla modern HTML5, CSS3, and JavaScript (no heavy node build steps required).

1. Serve the `frontend/` directory using any HTTP server:
   ```bash
   # Using Python:
   cd frontend
   python -m http.server 5500
   
   # Or using VS Code "Live Server" extension on port 5500.
   ```
2. Open your browser:
   - **Driver Web Application**: `http://localhost:5500/index.html`
   - **Admin Management Portal**: `http://localhost:5500/admin.html`

> [!TIP]
> The frontend auto-detects `localhost` or `127.0.0.1` and points requests to `http://127.0.0.1:5000`. In production, it points to your deployed backend URL.

---

### 4. ESP32 Firmware Setup

1. Open **Arduino IDE**.
2. Navigate to **File > Preferences** and add the ESP32 boards manager URL:
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
3. Install **ESP32 by Espressif Systems** from the Boards Manager.
4. Open the Library Manager (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>I</kbd>) and install:
   - `ArduinoJson` (v6 or v7)
   - `ESP32Servo`
5. Open `esp32/ParkEaseEntryClient/ParkEaseEntryClient.ino`.
6. Copy `esp32/secrets.h.example` to `esp32/ParkEaseEntryClient/secrets.h`:
   ```cpp
   constexpr char WIFI_SSID[] = "Your_WiFi_SSID";
   constexpr char WIFI_PASSWORD[] = "Your_WiFi_Password";
   // Use your computer's local LAN IPv4 address (NOT 127.0.0.1)
   constexpr char API_BASE_URL[] = "http://192.168.1.50:5000";
   constexpr char IOT_API_KEY[] = "your-hardware-shared-api-key";
   ```
7. Connect your ESP32 via micro-USB, select the appropriate COM port and board (**ESP32 Dev Module**), and click **Upload**.

---

## 📡 RESTful API Reference

### Public / User Endpoints
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/slots` | Retrieve status of all slots (`S1`, `S2`, `S3`) | No |
| `POST` | `/api/book` | Reserve an available slot (Concurrency safe) | Optional |
| `POST` | `/api/cancel` | Cancel an active reservation | Optional |
| `POST` | `/api/enter-parking` | Request barrier gate authorization | Optional |
| `GET` | `/api/booking-status` | Poll status of a specific booking ID | No |
| `GET` | `/api/entry-status` | Check if a vehicle is waiting at the entrance | No |
| `POST` | `/api/auth/register` | Register a new user account | No |
| `POST` | `/api/auth/login` | User login (returns JWT token) | No |
| `GET` | `/api/auth/me` | Fetch authenticated user profile & active booking | Bearer JWT |

### Hardware (ESP32) Endpoints
> *All hardware endpoints require the HTTP header `X-IoT-Key: <IOT_API_KEY>`.*

| Method | Endpoint | Description | Payload / Response |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/iot/entry` | Transmit entry IR sensor state | `{"vehicle_waiting": true/false}` |
| `GET` | `/api/iot/entry-status`| Atomically check and consume gate authorization | `{"authorized": true/false}` |
| `POST` | `/api/iot/entry-crossed`| Signal vehicle has cleared the entrance gate | Trigger exit sequence completion |
| `POST` | `/api/iot/slots` | Update slot IR sensor states in bulk | `{"slots": {"S1": true, "S2": false}}` |
| `POST` | `/api/iot/exit` | Report exit IR barrier trigger | Initiates exit sequence |

### Admin Endpoints
> *All admin routes require an Admin JWT via `Authorization: Bearer <TOKEN>`.*

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/admin/login` | Authenticate admin credentials |
| `GET` | `/api/admin/dashboard` | Aggregated statistics, occupancy rates, and active states |
| `GET` | `/api/admin/bookings` | Historical and active booking audit trail |
| `GET` | `/api/admin/vehicles` | Real-time directory of vehicles currently parked |
| `GET` | `/api/admin/iot-status`| Live heartbeat and IR sensor state telemetry |
| `POST` | `/api/admin/simulate-sensor` | Manual sensor override trigger for live testing |

---

## 🚢 Deployment Guide

### Backend & Database (Render.com)
The project includes a root `render.yaml` blueprint:
1. Push the repository to GitHub.
2. In [Render.com](https://render.com), create a **New Blueprint Instance** and link your repository.
3. Render automatically provisions:
   - A managed **PostgreSQL** database.
   - A **Python Web Service** running Gunicorn: `gunicorn run:app --bind 0.0.0.0:$PORT`.
4. Define your production environment variables (`IOT_API_KEY`, `CORS_ORIGINS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`).

### Frontend (Vercel)
1. Import the repository into [Vercel](https://vercel.com).
2. Set the **Root Directory** to `frontend`.
3. Deploy! Vercel serves the static dashboard globally with instant CDN cache invalidation.

---

## 🔒 Security & Concurrency Design

1. **Race-Condition Prevention**: Simultaneous booking requests are handled via SQL row locks (`with_for_update()`). Only the first commited transaction succeeds; simultaneous requests receive an immediate HTTP 409 Conflict.
2. **Double-Booking Database Constraint**: A dedicated `active_slot_id` column with a `UNIQUE` constraint guarantees that no database state can store two simultaneous active bookings for the same parking bay.
3. **Constant-Time Hardware Auth**: Header tokens from the ESP32 are evaluated using `hmac.compare_digest()` to eliminate timing-attack vulnerabilities.
4. **Credential Safety**: User and administrator passwords are encrypted using `werkzeug.security` (PBKDF2-HMAC-SHA256).

---

## 🤝 Contributing & License

Contributions, bug reports, and hardware optimization PRs are welcome!
Distributed under the **MIT License**. See `LICENSE` for details.
