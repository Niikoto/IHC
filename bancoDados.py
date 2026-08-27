import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "lojas.db")

def create_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tables com schema mais complexo
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS estoque (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        produto TEXT UNIQUE, 
                        departamento TEXT,
                        data_fabricacao TEXT,
                        data_validade TEXT
                    )""")
        
        # INSERT or IGNORE precisa que o 'produto' seja UNIQUE para não duplicar
        c.executemany("""INSERT or IGNORE INTO estoque 
                         (produto, departamento, data_fabricacao, data_validade) 
                         VALUES(?, ?, ?, ?)""", [
            ("sabonete", "higiene", "2026-01-10", "2028-01-10"),
            ("agua", "bebidas", "2026-05-15", "2027-05-15"),
            ("coca", "bebidas", "2026-06-20", "2026-12-20"),
        ])

    except Exception as e:
        print(f"Erro no banco: {e}")
        return "Erro"

    conn.commit()
    conn.close()

# Executa e testa
if __name__ == "__main__":
    create_db()
    conn = sqlite3.connect(db_path)
    results = conn.execute("SELECT * from estoque").fetchall()
    print("Banco atualizado:")
    print(results)