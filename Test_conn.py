import psycopg2

dsn = "dbname=consultorio user=postgres password=582456489Mds host=localhost port=5432"
conn = psycopg2.connect(dsn)
print("✅ Conexión exitosa")
conn.close()