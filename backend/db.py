import duckdb
import os

DB_PATH = "index.db"


def init_db():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file_path = os.path.join(script_dir, 'db_init.sql')
    execute_sql_file(sql_file_path)


def execute(sql: str, params=None):
    con = duckdb.connect(DB_PATH)
    con.execute(sql, params)
    con.close()


def execute_sql_file(file_path: str):
    with open(file_path, 'r') as f:
        sql_script = f.read()
    execute(sql_script)


def fetch_all(sql: str, params=None) -> list:
    con = duckdb.connect(DB_PATH)
    result = con.execute(sql, params).fetchall()
    con.close()
    return result


def get_seq_current_val(seq_name: str) -> int:
    con = duckdb.connect(DB_PATH)
    result =  con.execute(f"SELECT currval('{seq_name}');").fetchone()[0]
    con.close()
    return result
