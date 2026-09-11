# ParkEase backend

This Flask service owns booking decisions and connects to MySQL; browsers and the ESP32 never connect to MySQL directly.

## Local setup

1. Create a virtual environment and install dependencies:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env`, set either `DATABASE_URL` or all `MYSQL_*` values, and set real `SECRET_KEY` and `IOT_API_KEY` values.
3. Create the schema, physical slots, and persisted gate state once:

   ```powershell
   flask --app run.py init-db
   ```

4. Run the API:

   ```powershell
   flask --app run.py run --debug
   ```

## Implemented API

- `GET /health`
- `GET /api/slots`
- `POST /api/book` with `name`, `phone`, `vehicle_number`, and `slot`
- `POST /api/cancel` with `booking_id`
- `POST /api/enter-parking` with `booking_id`; requires a sensor report and
  creates a single pending authorization.
- `POST /api/iot/entry` with `vehicle_waiting` (`true` or `false`).
- `GET /api/iot/entry-status`; atomically returns and consumes one pending
  authorization for the gate. Both IoT routes require the `X-IoT-Key` header
  to match `IOT_API_KEY`.

`POST /api/book` locks the selected MySQL slot row (`SELECT ... FOR UPDATE`) and uses a unique active-booking slot key as a second database guard. This makes one concurrent attempt succeed and the rest receive HTTP 409.

Run tests from this directory with `pytest`. Tests use a temporary SQLite database only; production configuration requires MySQL.

After pulling entry-authorization changes into an existing local database, run
`flask --app run.py init-db` once to create the `parking_system_state` table.
