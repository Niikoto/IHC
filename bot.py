import sqlite3
import dspy
import os
import telebot 
import whisper
import json
import API_TOKEN
import bancoDados


bancoDados.create_db()


lm = dspy.LM('openai/gemma-4-E2B-it-IQ4_XS', api_base='http://localhost:1337/v1', api_key='not-needed')
dspy.configure(lm=lm)

class TextToSQL(dspy.Signature):
    """Generate SQL from natural language.

        Database schema:
          - estoque: id, produto, departamento, data_fabricacao, data_validade
    """
    dbschema = dspy.InputField(desc="Databases schema")
    question = dspy.InputField(desc="Natural language question")
    sql_query = dspy.OutputField(desc="Valid SQL query")

class ReliableSQLGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_sql = dspy.ChainOfThought(TextToSQL)

    def forward(self, schema, question):
        pred = self.generate_sql(schema=schema, question=question)
        return pred

#REQUISITOS 2 e 3
def validar_sql(sql_query):
    # Requisito 3: Checagem de execução apenas de SELECT
    if not sql_query.strip().upper().startswith("SELECT"):
        return False, "Operação negada: Apenas consultas (SELECT) são permitidas."
    
    # Requisito 2: Try/catch em um sqlite in-memory para pegar exceptions
    try:
        mem_conn = sqlite3.connect(':memory:')
        mem_c = mem_conn.cursor()
        
        # Cria o mesmo schema na memória para o SQLite reconecer as colunas
        mem_c.execute("""
            CREATE TABLE estoque (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto TEXT UNIQUE, 
                departamento TEXT,
                data_fabricacao TEXT,
                data_validade TEXT
            )
        """)
        
        # Tenta executar a query gerada (a tabela ta vazia em teoria, ai ela testa apenas a sintaxe)
        mem_c.execute(sql_query)
        mem_conn.close()
        return True, "SQL Válido"
    except sqlite3.Error as e:
        return False, f"Erro de sintaxe no SQL gerado: {e}"

def generate(question):
    schema = """
    CREATE TABLE estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto TEXT UNIQUE, 
        departamento TEXT,
        data_fabricacao TEXT,
        data_validade TEXT
    );
    """
    generator = ReliableSQLGenerator()
    resultado_ia = generator.forward(schema, question)
    sql_gerado = resultado_ia.sql_query
    
    print(f"SQL Gerado pela IA: {sql_gerado}")
    
    # Valida o SQL gerado antes de executar no banco real
    is_valid, msg = validar_sql(sql_gerado)
    
    if not is_valid:
        return {"erro": msg, "sql_tentado": sql_gerado}
    
    # Se passou na segurança, executa no banco real
    try:
        conn = sqlite3.connect(bancoDados.db_path)
        conn.row_factory = sqlite3.Row # Para retornar como dicionário
        results = conn.execute(sql_gerado).fetchall()
        conn.close()
        return [dict(row) for row in results]
    except Exception as e:
        return {"erro": f"Erro ao executar no banco real: {e}"}

# configuração do bot do Telegram
API_KEY = API_TOKEN.darToken()
bot = telebot.TeleBot(API_KEY)

@bot.message_handler(func=lambda message: True)
def reply_hi(message):
    bot.reply_to(message, "Gerando consulta, aguarde...")
    result = generate(message.text)
    # Formata a saída com indentação para ficar bonitinho no Telegram
    bot.reply_to(message, json.dumps(result, indent=2, ensure_ascii=False))

@bot.message_handler(content_types=['voice'])
def transcribe_voice_message(message):
    bot.reply_to(message, "Áudio recebido! Transcrevendo...")
    
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    audio_path = "temp_audio.ogg"
    with open(audio_path, 'wb') as new_file:
        new_file.write(downloaded_file)
    
    # Transcreve
    text = whisper_transcribe(audio_path)
    
    # Apaga o áudio temporário para não lotar o HD
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    bot.reply_to(message, f"Você disse: '{text}'. Buscando no banco...")
    
    result = generate(text)
    bot.reply_to(message, json.dumps(result, indent=2, ensure_ascii=False))

def whisper_transcribe(filepath: str, model="tiny") -> str:
    modelo = whisper.load_model(model)
    result = modelo.transcribe(filepath)
    return result["text"]

print("Bot rodando, Mande uma mensagem lá no Telegram my friend...")
bot.polling()