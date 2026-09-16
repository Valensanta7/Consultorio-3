from db import ensure_schema, get_connection


conn = get_connection()
print("Conexion exitosa")
conn.close()

ensure_schema()
print("Esquema verificado")
