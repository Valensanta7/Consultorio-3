from flask import flash, redirect, request, url_for

from core import app, get_db
from helpers import parse_date, parse_time


@app.route("/paciente/<int:id_paciente>/turno/guardar", methods=["POST"])
def guardar_turno(id_paciente):
    fecha = parse_date(request.form.get("fecha", "").strip())
    hora = parse_time(request.form.get("hora", "").strip())
    motivo = request.form.get("motivo", "").strip()
    notas = request.form.get("notas", "").strip()

    if not fecha or not hora:
        return "La fecha y la hora del turno son obligatorias.", 400

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM pacientes WHERE id = %s", (id_paciente,))
        if not cur.fetchone():
            return f"Paciente con ID {id_paciente} no encontrado", 404

        cur.execute(
            """
            INSERT INTO turnos (id_paciente, fecha, hora, motivo, estado, notas)
            VALUES (%s, %s, %s, %s, 'pendiente', %s)
            """,
            (id_paciente, fecha, hora, motivo or None, notas or None),
        )
    conn.commit()
    flash("Turno guardado correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/paciente/<int:id_paciente>/turno/<int:id_turno>/estado", methods=["POST"])
def actualizar_estado_turno(id_paciente, id_turno):
    nuevo_estado = request.form.get("estado", "").strip().lower()
    estados_validos = {"pendiente", "realizado", "cancelado"}
    if nuevo_estado not in estados_validos:
        return "Estado de turno inválido.", 400

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE turnos
            SET estado = %s
            WHERE id = %s AND id_paciente = %s
            """,
            (nuevo_estado, id_turno, id_paciente),
        )
    conn.commit()
    flash("Estado del turno actualizado.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))
