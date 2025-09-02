from flask import Flask, redirect, request, render_template, url_for
from db import get_connection

app = Flask(__name__)

# Pantalla de búsqueda / inicio
@app.route('/')
def index():
    return render_template('index.html')


# Endpoint para buscar pacientes por nombre o apellido
@app.route('/buscar')
def buscar():
    query = request.args.get('query')
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, nombre, apellido
        FROM pacientes
        WHERE nombre ILIKE %s OR apellido ILIKE %s
        """,
        (f'%{query}%', f'%{query}%')
    )
    resultados = cur.fetchall()
    cur.close()
    conn.close()

    # Generamos HTML directo (podés luego pasarlo a plantilla)
    html = "<h1>Resultados de búsqueda</h1><ul>"
    for id_paciente, nombre, apellido in resultados:
        link = url_for('ficha_form', id_paciente=id_paciente)
        html += f"<li>{nombre} {apellido} - <a href='{link}'>Ver ficha</a></li>"
    html += "</ul><a href='/'>Volver al inicio</a>"
    return html


# Formulario para ver/crear ficha de un paciente
@app.route('/ficha/<int:id_paciente>')
def ficha_form(id_paciente):
    conn = get_connection()
    cur = conn.cursor()

    # Traigo nombre y apellido del paciente
    cur.execute("SELECT nombre, apellido FROM pacientes WHERE id = %s", (id_paciente,))
    paciente = cur.fetchone()

    cur.close()
    conn.close()

    if not paciente:
        return f"Paciente con ID {id_paciente} no encontrado", 404

    return render_template(
        'ficha.html',
        id_paciente=id_paciente,
        paciente=paciente
    )


# Guardar la ficha y redirigir de vuelta al formulario
@app.route('/guardar_ficha', methods=['POST'])
def guardar_ficha():
    form = request.form
    id_paciente   = form.get('id_paciente')
    diagnostico   = form.get('diagnostico')
    tratamiento   = form.get('tratamiento')
    estudios      = form.get('estudios')
    observaciones = form.get('observaciones')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO fichas (
            id_paciente, diagnostico, tratamiento,
            estudios, observaciones
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        (id_paciente, diagnostico, tratamiento, estudios, observaciones)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('ficha_form', id_paciente=id_paciente))


if __name__ == '__main__':
    app.run(debug=True)