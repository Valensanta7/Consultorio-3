from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for

from core import app, get_db
from helpers import (
    HORARIOS_TURNO,
    obtener_estudios,
    obtener_ficha,
    obtener_historial,
    obtener_turnos,
    paciente_o_404,
    parse_date,
)


@app.route("/ficha/<int:id_paciente>")
def ficha_form(id_paciente):
    with get_db().cursor() as cur:
        paciente = paciente_o_404(cur, id_paciente)
        historial = obtener_historial(cur, id_paciente)
        estudios_adjuntos = obtener_estudios(cur, id_paciente)
        turnos = obtener_turnos(cur, id_paciente)

    return render_template(
        "ficha.html",
        id_paciente=id_paciente,
        paciente=paciente,
        historial=historial,
        estudios_adjuntos=estudios_adjuntos,
        turnos=turnos,
        hoy=date.today().strftime("%Y-%m-%d"),
        horarios_turno=HORARIOS_TURNO,
    )


@app.route("/guardar_ficha", methods=["POST"])
def guardar_ficha():
    id_paciente = request.form.get("id_paciente")
    fecha_atencion = parse_date(request.form.get("fecha_atencion", "").strip()) or date.today()
    guarda = request.form.get("guarda", "").strip()

    if not id_paciente:
        abort(400, description="Falta el paciente asociado a la ficha.")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fichas (id_paciente, fecha_atencion, guarda)
            VALUES (%s, %s, %s)
            """,
            (id_paciente, fecha_atencion, guarda),
        )
    conn.commit()

    flash("Ficha guardada correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/ficha/<int:id_paciente>/editar/<int:id_ficha>")
def editar_ficha_form(id_paciente, id_ficha):
    with get_db().cursor() as cur:
        paciente = paciente_o_404(cur, id_paciente)
        ficha = obtener_ficha(cur, id_ficha, id_paciente)

    if not ficha:
        abort(404, description=f"Ficha con ID {id_ficha} no encontrada.")

    return render_template(
        "editar_ficha.html",
        paciente=paciente,
        ficha=ficha,
        id_paciente=id_paciente,
    )


@app.route("/ficha/<int:id_paciente>/guardar/<int:id_ficha>", methods=["POST"])
def actualizar_ficha(id_paciente, id_ficha):
    fecha_atencion = parse_date(request.form.get("fecha_atencion", "").strip()) or date.today()
    guarda = request.form.get("guarda", "").strip()

    conn = get_db()
    with conn.cursor() as cur:
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

    flash("Ficha actualizada correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/eliminar_ficha/<int:id_ficha>/<int:id_paciente>", methods=["POST"])
def eliminar_ficha(id_ficha, id_paciente):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM fichas WHERE id = %s AND id_paciente = %s",
            (id_ficha, id_paciente),
        )
    conn.commit()
    flash("Ficha eliminada.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))
