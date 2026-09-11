import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


# Load backend/.env before Config reads database settings. Existing environment
# variables still take precedence over values in the file.
load_dotenv()


def _database_url() -> str:
    """Return an explicit URL first, otherwise build a MySQL URL from env."""
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        # Render provides postgres:// which SQLAlchemy needs as postgresql://
        if configured_url.startswith("postgres://"):
            return configured_url.replace("postgres://", "postgresql+psycopg2://", 1)
        if configured_url.startswith("postgresql://"):
            return configured_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        # Some hosting platforms expose the legacy mysql:// scheme.
        if configured_url.startswith("mysql://"):
            return configured_url.replace("mysql://", "mysql+pymysql://", 1)
        return configured_url

    required = ("MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Database configuration is missing. Set DATABASE_URL or: "
            + ", ".join(missing)
        )

    host = os.environ["MYSQL_HOST"]
    port = os.getenv("MYSQL_PORT", "3306")
    database = quote_plus(os.environ["MYSQL_DATABASE"])
    user = quote_plus(os.environ["MYSQL_USER"])
    password = quote_plus(os.environ["MYSQL_PASSWORD"])
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    IOT_API_KEY = os.getenv("IOT_API_KEY")
    CORS_ORIGINS = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",")
        if origin.strip()
    )
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@parkease.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")

