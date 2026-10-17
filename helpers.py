from datetime import date, datetime

from core import UPLOAD_DIR

HORARIOS_TURNO = [
    f"{hora:02d}:{minuto:02d}"
    for hora in range(8, 20)
    for minuto in (0, 15, 30, 45)
] + ["20:00"]


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
        SELECT id, id_paciente, fecha_atencion, guarda, created_at
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
        SELECT id, fecha_atencion, guarda, created_at
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
