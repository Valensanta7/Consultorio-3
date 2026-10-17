import uuid
from pathlib import Path

from flask import abort, flash, redirect, request, send_file, url_for
from werkzeug.utils import secure_filename

from core import UPLOAD_DIR, app, ensure_upload_dir, get_db


@app.route("/paciente/<int:id_paciente>/subir_estudio", methods=["POST"])
def subir_estudio(id_paciente):
    archivo = request.files.get("archivo_estudio")
    descripcion = request.form.get("descripcion", "").strip()

    if not archivo or not archivo.filename:
        abort(400, description="Tenés que seleccionar un archivo de estudio.")

    ensure_upload_dir()
    nombre_original = archivo.filename
    nombre_limpio = secure_filename(nombre_original) or "estudio"
    sufijo = Path(nombre_limpio).suffix
    nombre_guardado = f"{uuid.uuid4().hex}{sufijo}"
    destino = UPLOAD_DIR / nombre_guardado
    archivo.save(destino)

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM pacientes WHERE id = %s", (id_paciente,))
        if not cur.fetchone():
            if destino.exists():
                destino.unlink()
            abort(404, description=f"Paciente con ID {id_paciente} no encontrado.")

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

    flash("Estudio adjunto guardado correctamente.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))


@app.route("/estudio/<int:id_estudio>/descargar")
def descargar_estudio(id_estudio):
    with get_db().cursor() as cur:
        cur.execute(
            """
            SELECT id, nombre_original, nombre_guardado, content_type
            FROM estudios_adjuntos
            WHERE id = %s
            """,
            (id_estudio,),
        )
        estudio = cur.fetchone()

    if not estudio:
        abort(404, description="Estudio no encontrado.")

    path = UPLOAD_DIR / estudio["nombre_guardado"]
    if not path.exists():
        abort(404, description="El archivo del estudio no existe en disco.")

    return send_file(
        path,
        as_attachment=True,
        download_name=estudio["nombre_original"],
        mimetype=estudio.get("content_type") or "application/octet-stream",
    )


@app.route("/estudio/<int:id_estudio>/eliminar/<int:id_paciente>", methods=["POST"])
def eliminar_estudio(id_estudio, id_paciente):
    conn = get_db()
    with conn.cursor() as cur:
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

    if estudio:
        path = UPLOAD_DIR / estudio["nombre_guardado"]
        if path.exists():
            path.unlink()

    flash("Estudio eliminado.", "success")
    return redirect(url_for("ficha_form", id_paciente=id_paciente))
