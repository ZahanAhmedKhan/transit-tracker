import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Open a connection to PostgreSQL using the settings in .env.

    If DATABASE_URL is set (the Supabase connection string), it is used.
    Otherwise the separate local settings DB_HOST, DB_PORT, DB_NAME,
    DB_USER and DB_PASSWORD are used, as in Phase 1.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url)

    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
