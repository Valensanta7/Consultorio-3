import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname='consultorio',
        user='postgres',
        password='582456489Mds',
        host='localhost',
        port='5432'
    )