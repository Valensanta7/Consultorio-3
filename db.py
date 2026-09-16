import os

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash


def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "consultorio"),
        user=os.getenv("DB_USER", "valentinsantamaria"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        cursor_factory=RealDictCursor,
    )


def ensure_schema():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pacientes (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(120) NOT NULL,
            apellido VARCHAR(120) NOT NULL
        );
        """
    )

    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS dni VARCHAR(32);")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS direccion TEXT;")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS telefono VARCHAR(64);")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE;")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS obra_social VARCHAR(120);")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS alergias TEXT;")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS antecedentes TEXT;")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS medicacion_habitual TEXT;")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS observaciones_generales TEXT;")
    cur.execute("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS pacientes_dni_unique_idx ON pacientes (dni) WHERE dni IS NOT NULL;")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fichas (
            id SERIAL PRIMARY KEY,
            id_paciente INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            diagnostico TEXT,
            tratamiento TEXT,
            estudios TEXT,
            observaciones TEXT,
            fecha TIMESTAMP DEFAULT NOW()
        );
        """
    )

    cur.execute("ALTER TABLE fichas ADD COLUMN IF NOT EXISTS fecha_atencion DATE;")
    cur.execute("ALTER TABLE fichas ADD COLUMN IF NOT EXISTS guarda TEXT;")
    cur.execute("ALTER TABLE fichas ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();")
    cur.execute("UPDATE fichas SET created_at = COALESCE(created_at, fecha, NOW());")
    cur.execute("UPDATE fichas SET fecha_atencion = COALESCE(fecha_atencion, DATE(fecha), CURRENT_DATE);")
    cur.execute("CREATE INDEX IF NOT EXISTS fichas_paciente_fecha_idx ON fichas (id_paciente, fecha_atencion DESC, created_at DESC);")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS estudios_adjuntos (
            id SERIAL PRIMARY KEY,
            id_paciente INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            descripcion TEXT,
            nombre_original TEXT NOT NULL,
            nombre_guardado TEXT NOT NULL,
            content_type VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS estudios_adjuntos_paciente_idx
        ON estudios_adjuntos (id_paciente, created_at DESC, id DESC);
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            nombre_mostrado VARCHAR(120),
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )

    default_username = os.getenv("APP_DEFAULT_USERNAME", "admin")
    default_password = os.getenv("APP_DEFAULT_PASSWORD", "admin123")
    default_display_name = os.getenv("APP_DEFAULT_DISPLAY_NAME", "Administrador")

    cur.execute("SELECT id FROM usuarios WHERE username = %s", (default_username,))
    existing_user = cur.fetchone()
    if not existing_user:
        cur.execute(
            """
            INSERT INTO usuarios (username, nombre_mostrado, password_hash)
            VALUES (%s, %s, %s)
            """,
            (
                default_username,
                default_display_name,
                generate_password_hash(default_password),
            ),
        )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS turnos (
            id SERIAL PRIMARY KEY,
            id_paciente INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            fecha DATE NOT NULL,
            hora TIME NOT NULL,
            motivo TEXT,
            estado VARCHAR(30) NOT NULL DEFAULT 'pendiente',
            notas TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS turnos_fecha_hora_idx
        ON turnos (fecha ASC, hora ASC, id ASC);
        """
    )

    conn.commit()
    cur.close()
    conn.close()
