import os
import sqlite3
import bot
from fastapi import FastAPI

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "lojas.db")


def create_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS estoque (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto TEXT UNIQUE,
                preco REAL,
                departamento TEXT,
                data_fabricacao TEXT,
                data_validade TEXT
            )
        """)

        c.executemany("""
            INSERT OR IGNORE INTO estoque
            (produto, preco, departamento, data_fabricacao, data_validade)
            VALUES (?, ?, ?, ?, ?)
        """, [
            ("sabonete", 2.30, "higiene", "2026-01-10", "2028-01-10"),
            ("agua", 2, "bebidas", "2026-05-15", "2027-05-15"),
            ("coca", 5.50, "bebidas", "2026-06-20", "2026-12-20"),
        ])

    except Exception as e:
        print(f"Erro no banco: {e}")
        return "Erro"

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def obter_estoque(question :str):
    results = bot.generate(question)

    return results