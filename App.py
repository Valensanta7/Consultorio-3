import os
import uuid
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from db import ensure_schema, get_connection

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def obtener_usuario_actual():
    if "user_id" not in session:
        return None

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, nombre_mostrado FROM usuarios WHERE id = %s",
        (session["user_id"],),
    )
    usuario = cur.fetchone()
    cur.close()
    return dict(usuario) if usuario else None


def parse_date(value: str | None):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(value: str | None):
    if not value:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def calcular_edad(fecha_nacimiento):
    if not fecha_nacimiento:
        return "Edad no calculable"
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


def normalizar_paciente(row):
    if not row:
        return None
    paciente = dict(row)
    paciente["edad"] = calcular_edad(paciente.get("fecha_nacimiento"))
    return paciente


def normalizar_ficha(row):
    ficha = dict(row)
    fecha_atencion = ficha.get("fecha_atencion")
    ficha["fecha_atencion_texto"] = fecha_atencion.strftime("%Y-%m-%d") if fecha_atencion else ""

    guarda = ficha.get("guarda")
    if not guarda:
        partes = []
        if ficha.get("diagnostico"):
            partes.append(f"Diagnóstico: {ficha['diagnostico']}")
        if ficha.get("tratamiento"):
            partes.append(f"Tratamiento: {ficha['tratamiento']}")
        if ficha.get("estudios"):
            partes.append(f"Estudios: {ficha['estudios']}")
        if ficha.get("observaciones"):
            partes.append(f"Observaciones: {ficha['observaciones']}")
        ficha["guarda"] = "\n\n".join(partes)

    return ficha


def normalizar_estudio(row):
    estudio = dict(row)
    fecha = estudio.get("created_at")
    estudio["fecha_texto"] = fecha.strftime("%Y-%m-%d %H:%M") if fecha else ""
    return estudio


def normalizar_turno(row):
    turno = dict(row)
    fecha = turno.get("fecha")
    hora = turno.get("hora")
    turno["fecha_texto"] = fecha.strftime("%Y-%m-%d") if fecha else ""
    turno["hora_texto"] = hora.strftime("%H:%M") if hora else ""
    return turno


def obtener_paciente(cur, id_paciente):
    cur.execute(
        """
        SELECT
            id, nombre, apellido, dni, direccion,
            telefono, fecha_nacimiento, obra_social,
            alergias, antecedentes, medicacion_habitual, observaciones_generales
        FROM pacientes
        WHERE id = %s
        """,
        (id_paciente,),
    )
    return normalizar_paciente(cur.fetchone())


def obtener_ficha(cur, id_ficha, id_paciente):
    cur.execute(
        """
        SELECT
            id, id_paciente, fecha_atencion, guarda, diagnostico,
            tratamiento, estudios, observaciones, created_at
        FROM fichas
        WHERE id = %s AND id_paciente = %s
        """,
        (id_ficha, id_paciente),
    )
    row = cur.fetchone()
    if not row:
        return None
    return normalizar_ficha(row)


def obtener_historial(cur, id_paciente):
    cur.execute(
        """
        SELECT
            id, fecha_atencion, guarda, diagnostico,
            tratamiento, estudios, observaciones, created_at
        FROM fichas
        WHERE id_paciente = %s
        ORDER BY fecha_atencion DESC NULLS LAST, created_at DESC, id DESC
        """,
        (id_paciente,),
    )
    return [normalizar_ficha(row) for row in cur.fetchall()]


def obtener_estudios(cur, id_paciente):
    cur.execute(
        """
        SELECT id, descripcion, nombre_original, nombre_guardado, content_type, created_at
        FROM estudios_adjuntos
        WHERE id_paciente = %s
        ORDER BY created_at DESC, id DESC
        """,
        (id_paciente,),
    )
    return [normalizar_estudio(row) for row in cur.fetchall()]


def obtener_turnos(cur, id_paciente):
    cur.execute(
        """
        SELECT id, id_paciente, fecha, hora, motivo, estado, notas, created_at
        FROM turnos
        WHERE id_paciente = %s
        ORDER BY fecha DESC, hora DESC, id DESC
        """,
        (id_paciente,),
    )
    return [normalizar_turno(row) for row in cur.fetchall()]


def eliminar_archivos_estudios(nombre_guardado_list):
    for nombre_guardado in nombre_guardado_list:
        if not nombre_guardado:
            continue
        path = UPLOAD_DIR / nombre_guardado
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


# ── Hooks de Flask ────────────────────────────────────────────────────────────

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


# ── Rutas ─────────────────────────────────────────────────────────────────────

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

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, username, nombre_mostrado, password_hash
            FROM usuarios
            WHERE username = %s
            """,
            (username,),
        )
        usuario = cur.fetchone()
        cur.close()

        if usuario and check_password_hash(usuario["password_hash"], password):
            session["user_id"] = usuario["id"]
            session["username"] = usuario["username"]
            flash("Sesión iniciada correctamente.", "success")
            return redirect(next_url)

        error = "Usuario o contraseña incorrectos."

    return render_template("login.html", error=error, username=username, next_url=next_url)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor()

    hoy = date.today()

    cur.execute("SELECT COUNT(*) AS total FROM pacientes")
    total_pacientes = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM fichas")
    total_fichas = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM estudios_adjuntos")
    total_estudios = cur.fetchone()["total"]

    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM turnos
        WHERE fecha >= %s AND estado = 'pendiente'
        """,
        (hoy,),
    )
    total_turnos_pendientes = cur.fetchone()["total"]

    # Pacientes cargados más recientemente
    cur.execute(
        """
        SELECT id, nombre, apellido, dni
        FROM pacientes
        ORDER BY created_at DESC, id DESC
        LIMIT 10
        """
    )
    recientes = [dict(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT
            f.id,
            f.id_paciente,
            f.fecha_atencion,
            p.nombre,
            p.apellido,
            p.dni
        FROM fichas f
        JOIN pacientes p ON p.id = f.id_paciente
        ORDER BY f.fecha_atencion DESC NULLS LAST, f.created_at DESC, f.id DESC
        LIMIT 6
        """
    )
    fichas_recientes = []
    for row in cur.fetchall():
        item = dict(row)
        fecha = item.get("fecha_atencion")
        item["fecha_atencion_texto"] = fecha.strftime("%Y-%m-%d") if fecha else "Sin fecha"
        fichas_recientes.append(item)

    cur.execute(
        """
        SELECT
            e.id,
            e.id_paciente,
            e.descripcion,
            e.nombre_original,
            e.created_at,
            p.nombre,
            p.apellido
        FROM estudios_adjuntos e
        JOIN pacientes p ON p.id = e.id_paciente
        ORDER BY e.created_at DESC, e.id DESC
        LIMIT 6
        """
    )
    estudios_recientes = []
    for row in cur.fetchall():
        item = dict(row)
        created_at = item.get("created_at")
        item["created_at_texto"] = created_at.strftime("%Y-%m-%d %H:%M") if created_at else ""
        estudios_recientes.append(item)

    cur.execute(
        """
        SELECT
            t.id,
            t.id_paciente,
            t.fecha,
            t.hora,
            t.motivo,
            t.estado,
            p.nombre,
            p.apellido
        FROM turnos t
        JOIN pacientes p ON p.id = t.id_paciente
        WHERE t.fecha >= %s AND t.estado = 'pendiente'
        ORDER BY t.fecha ASC, t.hora ASC, t.id ASC
        LIMIT 8
        """,
        (hoy,),
    )
    proximos_turnos = [normalizar_turno(row) for row in cur.fetchall()]

    cur.close()
    return render_template(
        "index.html",
        recientes=recientes,
        total_pacientes=total_pacientes,
        total_fichas=total_fichas,
        total_estudios=total_estudios,
        total_turnos_pendientes=total_turnos_pendientes,
        fichas_recientes=fichas_recientes,
        estudios_recientes=estudios_recientes,
        proximos_turnos=proximos_turnos,
    )


@app.route("/buscar")
def buscar():
    query = request.args.get("query", "").strip()

    if not query:
        return render_template("buscar.html", query=query, resultados=[])

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, nombre, apellido, dni, telefono, obra_social
        FROM pacientes
        WHERE nombre ILIKE %s
           OR apellido ILIKE %s
           OR COALESCE(dni, '') ILIKE %s
        ORDER BY apellido, nombre
        """,
        (f"%{query}%", f"%{query}%", f"%{query}%"),
    )
    resultados = [dict(row) for row in cur.fetchall()]
    cur.close()

    return render_template("buscar.html", query=query, resultados=resultados)


@app.route("/nuevo_paciente")
def nuevo_paciente_form():
    return render_template("nuevo_paciente.html", hoy=date.today().strftime("%Y-%m-%d"))


@app.route("/guardar_paciente", methods=["POST"])
def guardar_paciente():
    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    dni = request.form.get("dni", "").strip()
    direccion = request.form.get("direccion", "").strip()
    telefono = request.form.get("telefono", "").strip()
    fecha_nacimiento = parse_date(request.form.get("fecha_nacimiento", "").strip())
    obra_social = request.form.get("obra_social", "").strip()

    if not nombre or not apellido or not dni:
        return "Faltan datos obligatorios: nombre, apellido y DNI.", 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pacientes WHERE dni = %s", (dni,))
    existente = cur.fetchone()
    if existente:
        cur.close()
        return redirect(url_for("ficha_form", id_paciente=existente["id"]))

    cur.execute(
        """
        INSERT INTO pacientes (
            nombre, apellido, dni, direccion,
            telefono, fecha_nacimiento, obra_social
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            nombre,
            apellido,
            dni,
            direccion or None,
            telefono or None,
            fecha_nacimiento,
            obra_social or None,
        ),
    )
    id_paciente = cur.fetchone()["id"]
    conn.commit()
    cur.close()

    flash("Paciente creado correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/editar")
def editar_paciente_form(id_paciente):
    conn = get_db()
    cur = conn.cursor()
    paciente = obtener_paciente(cur, id_paciente)
    cur.close()

    if not paciente:
        return f"Paciente con ID {id_paciente} no encontrado", 404

    return render_template("editar_paciente.html", paciente=paciente)


@app.route("/paciente/<int:id_paciente>/guardar", methods=["POST"])
def actualizar_paciente(id_paciente):
    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    dni = request.form.get("dni", "").strip()
    direccion = request.form.get("direccion", "").strip()
    telefono = request.form.get("telefono", "").strip()
    fecha_nacimiento = parse_date(request.form.get("fecha_nacimiento", "").strip())
    obra_social = request.form.get("obra_social", "").strip()
    alergias = request.form.get("alergias", "").strip()
    antecedentes = request.form.get("antecedentes", "").strip()
    medicacion_habitual = request.form.get("medicacion_habitual", "").strip()
    observaciones_generales = request.form.get("observaciones_generales", "").strip()

    if not nombre or not apellido or not dni:
        return "Faltan datos obligatorios: nombre, apellido y DNI.", 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM pacientes WHERE dni = %s AND id <> %s",
        (dni, id_paciente),
    )
    if cur.fetchone():
        cur.close()
        return "Ya existe otro paciente con ese DNI.", 400

    cur.execute(
        """
        UPDATE pacientes
        SET nombre = %s,
            apellido = %s,
            dni = %s,
            direccion = %s,
            telefono = %s,
            fecha_nacimiento = %s,
            obra_social = %s,
            alergias = %s,
            antecedentes = %s,
            medicacion_habitual = %s,
            observaciones_generales = %s
        WHERE id = %s
        """,
        (
            nombre,
            apellido,
            dni,
            direccion or None,
            telefono or None,
            fecha_nacimiento,
            obra_social or None,
            alergias or None,
            antecedentes or None,
            medicacion_habitual or None,
            observaciones_generales or None,
            id_paciente,
        ),
    )
    conn.commit()
    cur.close()
    flash("Datos del paciente actualizados.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/bloque_clinico", methods=["POST"])
def guardar_bloque_clinico(id_paciente):
    alergias = request.form.get("alergias", "").strip()
    antecedentes = request.form.get("antecedentes", "").strip()
    medicacion_habitual = request.form.get("medicacion_habitual", "").strip()
    observaciones_generales = request.form.get("observaciones_generales", "").strip()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE pacientes
        SET alergias = %s,
            antecedentes = %s,
            medicacion_habitual = %s,
            observaciones_generales = %s
        WHERE id = %s
        """,
        (
            alergias or None,
            antecedentes or None,
            medicacion_habitual or None,
            observaciones_generales or None,
            id_paciente,
        ),
    )
    conn.commit()
    cur.close()
    flash("Bloque clínico guardado.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/eliminar", methods=["POST"])
def eliminar_paciente(id_paciente):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT nombre_guardado FROM estudios_adjuntos WHERE id_paciente = %s",
        (id_paciente,),
    )
    archivos = [row["nombre_guardado"] for row in cur.fetchall()]

    cur.execute("DELETE FROM pacientes WHERE id = %s", (id_paciente,))
    conn.commit()
    cur.close()

    eliminar_archivos_estudios(archivos)
    flash("Paciente eliminado correctamente.", "success")
    return redirect(url_for("index"))


@app.route("/ficha/<int:id_paciente>")
def ficha_form(id_paciente):
    conn = get_db()
    cur = conn.cursor()

    paciente = obtener_paciente(cur, id_paciente)
    if not paciente:
        cur.close()
        return f"Paciente con ID {id_paciente} no encontrado", 404

    historial = obtener_historial(cur, id_paciente)
    estudios_adjuntos = obtener_estudios(cur, id_paciente)
    turnos = obtener_turnos(cur, id_paciente)
    cur.close()

    return render_template(
        "ficha.html",
        id_paciente=id_paciente,
        paciente=paciente,
        historial=historial,
        estudios_adjuntos=estudios_adjuntos,
        turnos=turnos,
        hoy=date.today().strftime("%Y-%m-%d"),
    )


@app.route("/guardar_ficha", methods=["POST"])
def guardar_ficha():
    id_paciente = request.form.get("id_paciente")
    fecha_atencion = parse_date(request.form.get("fecha_atencion", "").strip())
    guarda = request.form.get("guarda", "").strip()

    if not id_paciente:
        return "Falta el paciente asociado a la ficha.", 400

    if not fecha_atencion:
        fecha_atencion = date.today()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO fichas (
            id_paciente, fecha_atencion, guarda,
            diagnostico, tratamiento, estudios, observaciones
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (id_paciente, fecha_atencion, guarda, None, None, None, None),
    )
    conn.commit()
    cur.close()

    flash("Ficha guardada correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/turno/guardar", methods=["POST"])
def guardar_turno(id_paciente):
    fecha = parse_date(request.form.get("fecha", "").strip())
    hora = parse_time(request.form.get("hora", "").strip())
    motivo = request.form.get("motivo", "").strip()
    notas = request.form.get("notas", "").strip()

    if not fecha or not hora:
        return "La fecha y la hora del turno son obligatorias.", 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pacientes WHERE id = %s", (id_paciente,))
    if not cur.fetchone():
        cur.close()
        return f"Paciente con ID {id_paciente} no encontrado", 404

    cur.execute(
        """
        INSERT INTO turnos (id_paciente, fecha, hora, motivo, estado, notas)
        VALUES (%s, %s, %s, %s, 'pendiente', %s)
        """,
        (id_paciente, fecha, hora, motivo or None, notas or None),
    )
    conn.commit()
    cur.close()
    flash("Turno guardado correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/turno/<int:id_turno>/estado", methods=["POST"])
def actualizar_estado_turno(id_paciente, id_turno):
    nuevo_estado = request.form.get("estado", "").strip().lower()
    estados_validos = {"pendiente", "realizado", "cancelado"}
    if nuevo_estado not in estados_validos:
        return "Estado de turno inválido.", 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE turnos
        SET estado = %s
        WHERE id = %s AND id_paciente = %s
        """,
        (nuevo_estado, id_turno, id_paciente),
    )
    conn.commit()
    cur.close()
    flash("Estado del turno actualizado.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/ficha/<int:id_paciente>/editar/<int:id_ficha>")
def editar_ficha_form(id_paciente, id_ficha):
    conn = get_db()
    cur = conn.cursor()
    paciente = obtener_paciente(cur, id_paciente)
    ficha = obtener_ficha(cur, id_ficha, id_paciente)
    cur.close()

    if not paciente:
        return f"Paciente con ID {id_paciente} no encontrado", 404
    if not ficha:
        return f"Ficha con ID {id_ficha} no encontrada", 404

    return render_template(
        "editar_ficha.html",
        paciente=paciente,
        ficha=ficha,
        id_paciente=id_paciente,
    )


@app.route("/ficha/<int:id_paciente>/guardar/<int:id_ficha>", methods=["POST"])
def actualizar_ficha(id_paciente, id_ficha):
    fecha_atencion = parse_date(request.form.get("fecha_atencion", "").strip())
    guarda = request.form.get("guarda", "").strip()

    if not fecha_atencion:
        fecha_atencion = date.today()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE fichas
        SET fecha_atencion = %s,
            guarda = %s
        WHERE id = %s AND id_paciente = %s
        """,
        (fecha_atencion, guarda, id_ficha, id_paciente),
    )
    conn.commit()
    cur.close()

    flash("Ficha actualizada correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/exportar/html")
def exportar_historial_html(id_paciente):
    conn = get_db()
    cur = conn.cursor()
    paciente = obtener_paciente(cur, id_paciente)
    if not paciente:
        cur.close()
        return f"Paciente con ID {id_paciente} no encontrado", 404

    historial = obtener_historial(cur, id_paciente)
    estudios_adjuntos = obtener_estudios(cur, id_paciente)
    cur.close()

    return render_template(
        "export_historial.html",
        paciente=paciente,
        historial=historial,
        estudios_adjuntos=estudios_adjuntos,
        fecha_exportacion=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/paciente/<int:id_paciente>/exportar/pdf")
def exportar_historial_pdf(id_paciente):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return "Falta instalar reportlab para exportar PDF.", 500

    conn = get_db()
    cur = conn.cursor()
    paciente = obtener_paciente(cur, id_paciente)
    if not paciente:
        cur.close()
        return f"Paciente con ID {id_paciente} no encontrado", 404

    historial = obtener_historial(cur, id_paciente)
    estudios_adjuntos = obtener_estudios(cur, id_paciente)
    cur.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 46
    y = height - margin

    def nueva_pagina():
        nonlocal y
        pdf.showPage()
        y = height - margin
        pdf.setFont("Helvetica", 11)

    def escribir_linea(texto="", font_name="Helvetica", font_size=11, extra_gap=4):
        nonlocal y
        if y < 70:
            nueva_pagina()
        pdf.setFont(font_name, font_size)
        for linea in (texto.splitlines() if texto else [""]):
            if y < 70:
                nueva_pagina()
            pdf.drawString(margin, y, linea[:120])
            y -= font_size + extra_gap

    pdf.setTitle(f"Historial_{paciente['apellido']}_{paciente['nombre']}")
    escribir_linea("Historial Clinico", "Helvetica-Bold", 16, 8)
    escribir_linea(f"Paciente: {paciente['apellido']} {paciente['nombre']}")
    escribir_linea(f"DNI: {paciente.get('dni') or 'Sin cargar'}")
    escribir_linea(f"Direccion: {paciente.get('direccion') or 'Sin cargar'}")
    escribir_linea(f"Telefono: {paciente.get('telefono') or 'Sin cargar'}")
    escribir_linea(f"Fecha de nacimiento: {paciente.get('fecha_nacimiento') or 'Sin cargar'}")
    escribir_linea(f"Edad: {paciente.get('edad')}")
    escribir_linea(f"Obra social: {paciente.get('obra_social') or 'Sin cargar'}")
    escribir_linea(f"Exportado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    escribir_linea()
    escribir_linea("Estudios Adjuntos", "Helvetica-Bold", 13, 6)
    if estudios_adjuntos:
        for estudio in estudios_adjuntos:
            escribir_linea(f"- {estudio.get('descripcion') or estudio.get('nombre_original')}")
            escribir_linea(f"  Archivo: {estudio.get('nombre_original')}")
            escribir_linea(f"  Fecha: {estudio.get('fecha_texto')}")
    else:
        escribir_linea("No hay estudios adjuntos cargados.")
    escribir_linea()
    escribir_linea("Historial de Fichas", "Helvetica-Bold", 13, 6)
    if historial:
        for index, ficha in enumerate(historial, start=1):
            escribir_linea(f"Ficha {index} - {ficha.get('fecha_atencion_texto') or 'Sin fecha'}", "Helvetica-Bold", 12, 5)
            texto = ficha.get("guarda") or "Sin contenido clinico cargado."
            for parrafo in texto.splitlines() or [""]:
                escribir_linea(parrafo)
            escribir_linea()
    else:
        escribir_linea("No hay fichas cargadas para este paciente.")

    pdf.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"historial_{paciente['apellido']}_{paciente['nombre']}.pdf",
        mimetype="application/pdf",
    )


@app.route("/paciente/<int:id_paciente>/subir_estudio", methods=["POST"])
def subir_estudio(id_paciente):
    archivo = request.files.get("archivo_estudio")
    descripcion = request.form.get("descripcion", "").strip()

    if not archivo or not archivo.filename:
        return "Tenés que seleccionar un archivo de estudio.", 400

    ensure_upload_dir()
    nombre_original = archivo.filename
    nombre_limpio = secure_filename(nombre_original) or "estudio"
    sufijo = Path(nombre_limpio).suffix
    nombre_guardado = f"{uuid.uuid4().hex}{sufijo}"
    destino = UPLOAD_DIR / nombre_guardado
    archivo.save(destino)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pacientes WHERE id = %s", (id_paciente,))
    if not cur.fetchone():
        cur.close()
        if destino.exists():
            destino.unlink()
        return f"Paciente con ID {id_paciente} no encontrado", 404

    cur.execute(
        """
        INSERT INTO estudios_adjuntos (
            id_paciente, descripcion, nombre_original,
            nombre_guardado, content_type
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            id_paciente,
            descripcion or None,
            nombre_original,
            nombre_guardado,
            archivo.content_type or "application/octet-stream",
        ),
    )
    conn.commit()
    cur.close()

    flash("Estudio adjunto guardado correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/estudio/<int:id_estudio>/descargar")
def descargar_estudio(id_estudio):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, nombre_original, nombre_guardado, content_type
        FROM estudios_adjuntos
        WHERE id = %s
        """,
        (id_estudio,),
    )
    estudio = cur.fetchone()
    cur.close()

    if not estudio:
        return "Estudio no encontrado.", 404

    path = UPLOAD_DIR / estudio["nombre_guardado"]
    if not path.exists():
        return "El archivo del estudio no existe en disco.", 404

    return send_file(
        path,
        as_attachment=True,
        download_name=estudio["nombre_original"],
        mimetype=estudio.get("content_type") or "application/octet-stream",
    )


@app.route("/estudio/<int:id_estudio>/eliminar/<int:id_paciente>", methods=["POST"])
def eliminar_estudio(id_estudio, id_paciente):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT nombre_guardado
        FROM estudios_adjuntos
        WHERE id = %s AND id_paciente = %s
        """,
        (id_estudio, id_paciente),
    )
    estudio = cur.fetchone()
    if estudio:
        cur.execute(
            "DELETE FROM estudios_adjuntos WHERE id = %s AND id_paciente = %s",
            (id_estudio, id_paciente),
        )
        conn.commit()
    cur.close()

    if estudio:
        path = UPLOAD_DIR / estudio["nombre_guardado"]
        if path.exists():
            path.unlink()

    flash("Estudio eliminado.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/eliminar_ficha/<int:id_ficha>/<int:id_paciente>", methods=["POST"])
def eliminar_ficha(id_ficha, id_paciente):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM fichas WHERE id = %s AND id_paciente = %s",
        (id_ficha, id_paciente),
    )
    conn.commit()
    cur.close()
    flash("Ficha eliminada.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


if __name__ == "__main__":
    ensure_upload_dir()
    ensure_schema()
    app.run(debug=True)
