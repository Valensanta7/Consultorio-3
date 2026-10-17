import os
from pathlib import Path

from flask import Flask, g, redirect, request, session, url_for

from db import get_connection

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "consultorio3-dev-secret-key")

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads" / "estudios"


def ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Conexión a la BD ──────────────────────────────────────────────────────────
# Una sola conexión por request, compartida entre todas las funciones.
# Se cierra automáticamente al final del request via teardown.

def get_db():
    if "db" not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def obtener_usuario_actual():
    if "user_id" not in session:
        return None
    with get_db().cursor() as cur:
        cur.execute(
            "SELECT id, username, nombre_mostrado FROM usuarios WHERE id = %s",
            (session["user_id"],),
        )
        usuario = cur.fetchone()
    return dict(usuario) if usuario else None


@app.context_processor
def inject_auth_user():
    return {"auth_user": obtener_usuario_actual()}


@app.before_request
def require_login():
    public_endpoints = {"login", "logout"}
    if request.endpoint is None:
        return None
    if request.endpoint == "static":
        return None
    if request.endpoint in public_endpoints:
        return None
    if "user_id" not in session:
        return redirect(url_for("login", next=request.path))
    return None
