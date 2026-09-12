import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Strip the SQLAlchemy dialect prefix -- psycopg2 needs a plain DSN
raw_url = os.getenv("DATABASE_URL", "").replace("postgresql+psycopg2://", "postgresql://")

SQL = """
ALTER TABLE document_chunks
    ALTER COLUMN embedding TYPE vector(384)
    USING embedding::vector(384);
"""

def run():
    conn = psycopg2.connect(raw_url)
    conn.autocommit = True          # DDL does not run inside a transaction block
    try:
        with conn.cursor() as cur:
            cur.execute(SQL)
            print("Migration applied: embedding column is now vector(384).")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
