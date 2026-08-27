from fastapi import FastAPI
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "lojas.db")

app = FastAPI(title="API Text2SQL - Estoque")

# Função para criar a conexão com o banco de dados
def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Faz o sqlite retornar as colunas com os nomes (como um JSON)
    return conn

# Rota GET so pr expor o banco
@app.get("/estoque")
def obter_estoque():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Busca n banco
    estoque = c.execute("SELECT * FROM estoque").fetchall()
    conn.close()
    
    # Converte as linhas do banco para uma lista de dicionários
    return [dict(item) for item in estoque]