from datetime import date

from flask import render_template, request

from core import app, get_db
from helpers import normalizar_turno


@app.route("/")
def index():
    conn = get_db()
    hoy = date.today()

    with conn.cursor() as cur:
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
                f.id, f.id_paciente, f.fecha_atencion,
                p.nombre, p.apellido, p.dni
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
                e.id, e.id_paciente, e.descripcion, e.nombre_original, e.created_at,
                p.nombre, p.apellido
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
                t.id, t.id_paciente, t.fecha, t.hora, t.motivo, t.estado,
                p.nombre, p.apellido
            FROM turnos t
            JOIN pacientes p ON p.id = t.id_paciente
            WHERE t.fecha >= %s AND t.estado = 'pendiente'
            ORDER BY t.fecha ASC, t.hora ASC, t.id ASC
            LIMIT 8
            """,
            (hoy,),
        )
        proximos_turnos = [normalizar_turno(row) for row in cur.fetchall()]

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

    with get_db().cursor() as cur:
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

    return render_template("buscar.html", query=query, resultados=resultados)
