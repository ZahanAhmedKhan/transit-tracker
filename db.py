import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    # Reads the database settings from .env and opens a connection to PostgreSQL.
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
