import sqlite3
import os
import dspy

# 1. Configuração do LM (mesmo modelo usado para inferência e reflexão)
lm = dspy.LM('openai/google/gemma-4-e2b', api_base='http://localhost:1337/v1', api_key='not-needed')
dspy.configure(lm=lm)

# 2. Schema comum
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

# 3. Assinatura e Módulo
class TextToSQL(dspy.Signature):
    """Generate valid SQLite SELECT query from natural language."""
    dbschema = dspy.InputField(desc="Database schema")
    question = dspy.InputField(desc="Natural language question")
    sql_query = dspy.OutputField(desc="Valid SQL query starting with SELECT")

class ReliableSQLGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_sql = dspy.ChainOfThought(TextToSQL)

    def forward(self, schema, question):
        return self.generate_sql(dbschema=schema, question=question)

# 4. Dataset de Treino
trainset = [
    dspy.Example(
        schema=SCHEMA,
        question="Quais bebidas temos no estoque?",
        sql_query="SELECT * FROM estoque WHERE departamento = 'bebidas';"
    ).with_inputs("schema", "question"),
    dspy.Example(
        schema=SCHEMA,
        question="Qual o produto mais caro?",
        sql_query="SELECT produto, preco FROM estoque ORDER BY preco DESC LIMIT 1;"
    ).with_inputs("schema", "question"),
    dspy.Example(
        schema=SCHEMA,
        question="Tem algum produto vencendo em 2026?",
        sql_query="SELECT * FROM estoque WHERE data_validade LIKE '2026%';"
    ).with_inputs("schema", "question"),
    dspy.Example(
        schema=SCHEMA,
        question="Quantos itens de higiene existem?",
        sql_query="SELECT COUNT(*) AS total FROM estoque WHERE departamento = 'higiene';"
    ).with_inputs("schema", "question"),
]

# 5. Métrica com Feedback em Linguagem Natural para o GEPA
def sql_execution_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    pred_sql = getattr(pred, "sql_query", "").strip()
    
    if not pred_sql.upper().startswith("SELECT"):
        return dspy.Prediction(
            score=0.0,
            feedback=f"A query gerada deve começar obrigatoriamente com SELECT. Query recebida: '{pred_sql}'"
        )

    conn = sqlite3.connect(':memory:')
    c = conn.cursor()
    c.execute(SCHEMA)
    c.executemany(
        "INSERT INTO estoque (produto, preco, departamento, data_fabricacao, data_validade) VALUES (?, ?, ?, ?, ?)",
        [
            ("sabonete", 2.30, "higiene", "2026-01-10", "2028-01-10"),
            ("agua", 2.00, "bebidas", "2026-05-15", "2027-05-15"),
            ("coca", 5.50, "bebidas", "2026-06-20", "2026-12-20"),
        ]
    )

    try:
        gold_res = c.execute(gold.sql_query).fetchall()
        pred_res = c.execute(pred_sql).fetchall()
        conn.close()

        if gold_res == pred_res:
            return dspy.Prediction(score=1.0, feedback="SQL executado com sucesso e os dados retornados estão corretos.")
        else:
            return dspy.Prediction(
                score=0.0,
                feedback=f"O SQL executou sem erros, mas os dados retornados não bateram com o esperado. Esperado: {gold_res}, Recebido: {pred_res} para a query '{pred_sql}'."
            )
    except sqlite3.Error as e:
        conn.close()
        return dspy.Prediction(
            score=0.0,
            feedback=f"Erro de sintaxe SQLite ao executar a query '{pred_sql}': {e}"
        )

# 6. Compilação
if __name__ == "__main__":
    print("Iniciando otimização com GEPA...")

    # auto='light' usa um orçamento leve ideal para modelos locais
    teleprompter = dspy.GEPA(
        metric=sql_execution_metric,
        reflection_lm=lm,
        auto="light"
    )

    optimized_program = teleprompter.compile(
        student=ReliableSQLGenerator(),
        trainset=trainset
    )

    output_file = "sql_generator_optimized.json"
    optimized_program.save(output_file)
    print(f"\nOtimização concluída e salva em {output_file}!")