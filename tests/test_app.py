import io

import App


def _id_desde_location(response):
    return response.headers["Location"].rstrip("/").split("/")[-1]


def _crear_paciente(client, **overrides):
    datos = {
        "nombre": "Paciente",
        "apellido": "DePrueba",
        "dni": "10000001",
        "direccion": "",
        "telefono": "",
        "fecha_nacimiento": "",
        "obra_social": "",
    }
    datos.update(overrides)
    resp = client.post("/guardar_paciente", data=datos, follow_redirects=False)
    return _id_desde_location(resp)


def test_login_con_credenciales_invalidas(client):
    resp = client.post(
        "/login", data={"username": "admin", "password": "incorrecta"}, follow_redirects=True
    )
    assert "Usuario o contraseña incorrectos" in resp.get_data(as_text=True)


def test_ruta_protegida_redirige_a_login_sin_sesion(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_alta_paciente_con_dni_duplicado_no_crea_otro(logueado):
    id_1 = _crear_paciente(logueado, dni="30111222")
    id_2 = _crear_paciente(logueado, dni="30111222")
    assert id_1 == id_2


def test_eliminar_paciente_borra_en_cascada(logueado):
    id_paciente = _crear_paciente(logueado, dni="40222333")
    logueado.post(
        "/guardar_ficha",
        data={"id_paciente": id_paciente, "fecha_atencion": "2026-01-01", "guarda": "nota de prueba"},
    )

    logueado.post(f"/paciente/{id_paciente}/eliminar")

    resp = logueado.get(f"/ficha/{id_paciente}", follow_redirects=True)
    assert resp.status_code == 200
    assert "no encontrado" in resp.get_data(as_text=True)


def test_subir_estudio_adjunto(logueado):
    id_paciente = _crear_paciente(logueado, dni="50333444")
    pdf_falso = (io.BytesIO(b"%PDF-1.4 contenido de prueba"), "analisis.pdf")

    resp = logueado.post(
        f"/paciente/{id_paciente}/subir_estudio",
        data={"archivo_estudio": pdf_falso, "descripcion": "Analisis de sangre"},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Analisis de sangre" in resp.get_data(as_text=True)


def test_exportar_historial_a_pdf(logueado):
    id_paciente = _crear_paciente(logueado, dni="60444555")

    resp = logueado.get(f"/paciente/{id_paciente}/exportar/pdf")

    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"


def test_login_se_bloquea_tras_5_intentos_fallidos(client):
    for _ in range(5):
        client.post("/login", data={"username": "admin", "password": "mal"})

    resp = client.post("/login", data={"username": "admin", "password": "admin123"})

    assert "Demasiados intentos fallidos" in resp.get_data(as_text=True)


def test_bloqueo_no_se_evade_con_una_sesion_nueva(client):
    for _ in range(5):
        client.post("/login", data={"username": "admin", "password": "mal"})

    otro_cliente = App.app.test_client()
    resp = otro_cliente.post("/login", data={"username": "admin", "password": "admin123"})

    assert "Demasiados intentos fallidos" in resp.get_data(as_text=True)


def test_paciente_inexistente_redirige_con_mensaje(logueado):
    resp = logueado.get("/ficha/999999", follow_redirects=True)
    assert resp.status_code == 200
    assert "no encontrado" in resp.get_data(as_text=True)


def test_alta_paciente_sin_datos_obligatorios_redirige_con_mensaje(logueado):
    resp = logueado.post(
        "/guardar_paciente", data={"nombre": "", "apellido": "", "dni": ""}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert "Faltan datos obligatorios" in resp.get_data(as_text=True)


def test_bloqueo_no_afecta_a_otro_usuario(client):
    for _ in range(5):
        client.post("/login", data={"username": "admin", "password": "mal"})

    resp = client.post("/login", data={"username": "otro_usuario", "password": "cualquiera"})

    assert "Usuario o contraseña incorrectos" in resp.get_data(as_text=True)
    assert "Demasiados intentos" not in resp.get_data(as_text=True)
