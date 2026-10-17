import os
import sys
from pathlib import Path

# La base de pruebas es independiente de la real: así los tests pueden
# crear y borrar pacientes de mentira sin tocar datos reales.
os.environ.setdefault("DB_NAME", "consultorio_test")
os.environ.setdefault("APP_DEFAULT_USERNAME", "admin")
os.environ.setdefault("APP_DEFAULT_PASSWORD", "admin123")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2  # noqa: E402
import pytest  # noqa: E402

import App as app_module  # noqa: E402
import db as db_module  # noqa: E402


def _crear_base_test_si_no_existe():
    conn = psycopg2.connect(
        dbname="postgres",
        user=os.getenv("DB_USER", "valentinsantamaria"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (os.environ["DB_NAME"],))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{os.environ["DB_NAME"]}"')
    cur.close()
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def _preparar_esquema():
    _crear_base_test_si_no_existe()
    app_module.ensure_schema()
    yield


@pytest.fixture(autouse=True)
def _tablas_limpias():
    """Deja pacientes/fichas/turnos/estudios vacíos antes de cada test."""
    conn = db_module.get_connection()
    cur = conn.cursor()
    cur.execute("TRUNCATE turnos, estudios_adjuntos, fichas, pacientes RESTART IDENTITY CASCADE;")
    conn.commit()
    cur.close()
    conn.close()
    app_module.intentos_fallidos_login.clear()
    yield


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def logueado(client):
    client.post("/login", data={"username": "admin", "password": "admin123"})
    return client
