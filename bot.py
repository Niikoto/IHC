import sqlite3
import dspy
import os
import re
import telebot 
import whisper
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = telebot.TeleBot(TOKEN)

# Configuração LM
lm = dspy.LM('openai/gemma-4-E2B-it-IQ4_XS', api_base='http://localhost:1337/v1', api_key='not-needed')
dspy.configure(lm=lm)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "lojas.db")

SCHEMA = """
CREATE TABLE estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto TEXT UNIQUE, 
    preco REAL,
    departamento TEXT,
    data_fabricacao TEXT,
    data_validade TEXT
);
"""

class TextToSQL(dspy.Signature):
    """Generate valid SQLite SELECT query from natural language."""
    dbschema = dspy.InputField(desc="Database schema")
    question = dspy.InputField(desc="Natural language question")
    sql_query = dspy.OutputField(desc="Valid SQL query")

class ReliableSQLGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_sql = dspy.ChainOfThought(TextToSQL)

    def forward(self, schema, question):
        return self.generate_sql(dbschema=schema, question=question)

# Instâncias globais (carregadas 1 única vez em memória)
generator = ReliableSQLGenerator()
model_path = os.path.join(BASE_DIR, "sql_generator_optimized.json")
if os.path.exists(model_path):
    generator.load(model_path)
    print("Modelo DSPy otimizado carregado com sucesso.")

whisper_model = whisper.load_model("tiny")

def sanitizar_sql(raw_sql: str) -> str:
    # Remove blocos markdown caso o LM retorne ```sql ... ```
    sql = re.sub(r'```sql|```', '', raw_sql, flags=re.IGNORECASE).strip()
    return sql

def validar_sql(sql_query: str):
    if not sql_query.upper().startswith("SELECT"):
        return False, "Operação negada: Apenas consultas (SELECT) são permitidas."
    
    try:
        mem_conn = sqlite3.connect(':memory:')
        mem_c = mem_conn.cursor()
        mem_c.execute(SCHEMA)
        mem_c.execute(sql_query)
        mem_conn.close()
        return True, "SQL Válido"
    except sqlite3.Error as e:
        return False, f"Erro de sintaxe no SQL gerado: {e}"

def generate(question: str):
    pred = generator(schema=SCHEMA, question=question)
    sql_gerado = sanitizar_sql(pred.sql_query)
    
    print(f"SQL Gerado: {sql_gerado}")
    
    is_valid, msg = validar_sql(sql_gerado)
    if not is_valid:
        return {"erro": msg, "sql_tentado": sql_gerado}
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        results = conn.execute(sql_gerado).fetchall()
        conn.close()
        return [dict(row) for row in results]
    except Exception as e:
        return {"erro": f"Erro ao executar no banco real: {e}"}

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(func=lambda message: True)
def reply_text(message):
    bot.reply_to(message, "Processando consulta...")
    result = generate(message.text)
    bot.reply_to(message, json.dumps(result, indent=2, ensure_ascii=False))

@bot.message_handler(content_types=['voice'])
def transcribe_voice_message(message):
    bot.reply_to(message, "Áudio recebido! Processando...")
    
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    audio_path = f"temp_{message.id}.ogg"
    
    with open(audio_path, 'wb') as f:
        f.write(downloaded_file)
    
    try:
        res = whisper_model.transcribe(audio_path)
        text = res["text"].strip()
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
    bot.reply_to(message, f"Você disse: '{text}'")
    result = generate(text)
    bot.reply_to(message, json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    print("Bot rodando...")
    bot.infinity_polling()