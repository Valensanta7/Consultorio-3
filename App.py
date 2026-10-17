"""Punto de entrada de Consultorio3.

Las rutas viven repartidas por épica, cada una en su propio módulo
(auth, dashboard, pacientes, fichas, turnos, estudios, exportacion).
Importarlas acá alcanza para que se registren en `app` via @app.route.
"""

import os

from core import app, ensure_upload_dir
from db import ensure_schema

import auth  # noqa: F401
import dashboard  # noqa: F401
import pacientes  # noqa: F401
import fichas  # noqa: F401
import turnos  # noqa: F401
import estudios  # noqa: F401
import exportacion  # noqa: F401

if __name__ == "__main__":
    ensure_upload_dir()
    ensure_schema()
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode)
