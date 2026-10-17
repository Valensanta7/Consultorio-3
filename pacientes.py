from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for

from core import app, get_db
from helpers import eliminar_archivos_estudios, paciente_o_404, parse_date


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
        abort(400, description="Faltan datos obligatorios: nombre, apellido y DNI.")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM pacientes WHERE dni = %s", (dni,))
        existente = cur.fetchone()
        if existente:
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

    flash("Paciente creado correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/editar")
def editar_paciente_form(id_paciente):
    with get_db().cursor() as cur:
        paciente = paciente_o_404(cur, id_paciente)

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
        abort(400, description="Faltan datos obligatorios: nombre, apellido y DNI.")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pacientes WHERE dni = %s AND id <> %s",
            (dni, id_paciente),
        )
        if cur.fetchone():
            abort(400, description="Ya existe otro paciente con ese DNI.")

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
    flash("Datos del paciente actualizados.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/bloque_clinico", methods=["POST"])
def guardar_bloque_clinico(id_paciente):
    alergias = request.form.get("alergias", "").strip()
    antecedentes = request.form.get("antecedentes", "").strip()
    medicacion_habitual = request.form.get("medicacion_habitual", "").strip()
    observaciones_generales = request.form.get("observaciones_generales", "").strip()

    conn = get_db()
    with conn.cursor() as cur:
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
    flash("Bloque clínico guardado.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/eliminar", methods=["POST"])
def eliminar_paciente(id_paciente):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT nombre_guardado FROM estudios_adjuntos WHERE id_paciente = %s",
            (id_paciente,),
        )
        archivos = [row["nombre_guardado"] for row in cur.fetchall()]

        cur.execute("DELETE FROM pacientes WHERE id = %s", (id_paciente,))
    conn.commit()

    eliminar_archivos_estudios(archivos)
    flash("Paciente eliminado correctamente.", "success")
    return redirect(url_for("index"))
