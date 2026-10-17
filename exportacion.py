from datetime import datetime
from io import BytesIO

from flask import render_template, send_file

from core import app, get_db
from helpers import obtener_estudios, obtener_historial, obtener_paciente


@app.route("/paciente/<int:id_paciente>/exportar/html")
def exportar_historial_html(id_paciente):
    with get_db().cursor() as cur:
        paciente = obtener_paciente(cur, id_paciente)
        if not paciente:
            return f"Paciente con ID {id_paciente} no encontrado", 404

        historial = obtener_historial(cur, id_paciente)
        estudios_adjuntos = obtener_estudios(cur, id_paciente)

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

    with get_db().cursor() as cur:
        paciente = obtener_paciente(cur, id_paciente)
        if not paciente:
            return f"Paciente con ID {id_paciente} no encontrado", 404

        historial = obtener_historial(cur, id_paciente)
        estudios_adjuntos = obtener_estudios(cur, id_paciente)

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
