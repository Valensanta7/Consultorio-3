import time
from collections import defaultdict

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from core import app, get_db

# ── Protección contra fuerza bruta en el login ─────────────────────────────
# En memoria: alcanza para un consultorio chico de un solo proceso.
# Si el servidor se reinicia, los intentos registrados se pierden (no es grave).
MAX_INTENTOS_LOGIN = 5
VENTANA_INTENTOS_SEGUNDOS = 15 * 60  # 15 minutos
intentos_fallidos_login = defaultdict(list)


def registrar_intento_fallido(clave):
    intentos_fallidos_login[clave].append(time.time())


def login_bloqueado(clave):
    ahora = time.time()
    intentos = intentos_fallidos_login[clave]
    intentos[:] = [t for t in intentos if ahora - t < VENTANA_INTENTOS_SEGUNDOS]
    if len(intentos) < MAX_INTENTOS_LOGIN:
        return None
    segundos_restantes = VENTANA_INTENTOS_SEGUNDOS - (ahora - intentos[0])
    return max(1, int(segundos_restantes // 60) + 1)


def limpiar_intentos_login(clave):
    intentos_fallidos_login.pop(clave, None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    error = ""
    username = ""
    next_url = request.args.get("next") or request.form.get("next") or url_for("index")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        clave_intentos = f"{username.lower()}:{request.remote_addr}"

        minutos_espera = login_bloqueado(clave_intentos)
        if minutos_espera:
            error = (
                f"Demasiados intentos fallidos. Probá de nuevo en "
                f"{minutos_espera} minuto{'s' if minutos_espera != 1 else ''}."
            )
            return render_template("login.html", error=error, username=username, next_url=next_url)

        with get_db().cursor() as cur:
            cur.execute(
                """
                SELECT id, username, nombre_mostrado, password_hash
                FROM usuarios
                WHERE username = %s
                """,
                (username,),
            )
            usuario = cur.fetchone()

        if usuario and check_password_hash(usuario["password_hash"], password):
            limpiar_intentos_login(clave_intentos)
            session["user_id"] = usuario["id"]
            session["username"] = usuario["username"]
            flash("Sesión iniciada correctamente.", "success")
            return redirect(next_url)

        registrar_intento_fallido(clave_intentos)
        error = "Usuario o contraseña incorrectos."

    return render_template("login.html", error=error, username=username, next_url=next_url)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))
