import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, seed_slots
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
            "CORS_ORIGINS": (),
            "IOT_API_KEY": "test-iot-key",
            "SECRET_KEY": "test-secret-key",
            "ADMIN_EMAIL": "admin@parkease.com",
            "ADMIN_PASSWORD": "Admin123!",
        }
    )
    with app.app_context():
        db.create_all()
        seed_slots()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
