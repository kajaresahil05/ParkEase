import logging
import os
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import text

from .config import Config, _database_url
from .extensions import db
from .models import ParkingSlot, ParkingSystemState, User
from .routes import api



def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()

    db.init_app(app)
    app.register_blueprint(api)

    # Ensure service-level logs are visible in the console.
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("app").setLevel(logging.INFO)

    with app.app_context():
        try:
            db.create_all()
            ensure_schema_updates()
            seed_slots()
        except Exception as exc:
            logging.warning("Initial database setup notice: %s", exc)

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        allowed_origins = app.config["CORS_ORIGINS"]
        if origin and (origin in allowed_origins or "*" in allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Access-Token, X-IoT-Key"
        return response

    @app.get("/health")
    def health_check():
        return jsonify(success=True, status="ok")

    frontend_folder = os.path.abspath(os.path.join(app.root_path, "..", "..", "frontend"))

    @app.get("/")
    def serve_index():
        return send_from_directory(frontend_folder, "index.html")

    @app.get("/<path:filename>")
    def serve_frontend_files(filename):
        if os.path.exists(os.path.join(frontend_folder, filename)):
            return send_from_directory(frontend_folder, filename)
        return jsonify(success=False, message="File not found"), 404


    @app.cli.command("init-db")
    def init_db_command():
        """Create schema, run safe migrations and seed initial data."""
        db.create_all()
        ensure_schema_updates()
        seed_slots()
        print("Database initialized successfully.")

    return app


def ensure_schema_updates() -> None:
    """Ensure missing columns are created safely on existing database tables."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)

        if "users" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("users")]
            with db.engine.begin() as conn:
                if "email" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL"))
                if "password_hash" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL"))
                if "role" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'USER'"))
                if "password_reset_token_hash" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_token_hash VARCHAR(255) NULL"))
                if "password_reset_expires_at" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_expires_at TIMESTAMP NULL"))

        if "parking_system_state" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("parking_system_state")]
            if "last_iot_update" not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE parking_system_state ADD COLUMN last_iot_update TIMESTAMP NULL"))
    except Exception as exc:
        logging.warning("Schema migration notice: %s", exc)



def seed_slots() -> None:
    for slot_number in ("S1", "S2", "S3"):
        if not db.session.query(ParkingSlot).filter_by(slot_number=slot_number).first():
            db.session.add(ParkingSlot(slot_number=slot_number, status="AVAILABLE", sensor_status="EMPTY"))
    if not db.session.get(ParkingSystemState, 1):
        db.session.add(ParkingSystemState(id=1))
    db.session.commit()
