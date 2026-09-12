"""
migrate_chunk_index.py
──────────────────────
Adds the `chunk_index` integer column to the `document_chunks` table
for existing databases, with a default value of 0.

Usage
─────
  python scripts/migrate_chunk_index.py
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "").replace("postgresql+psycopg2://", "postgresql://")

SQL = """
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS chunk_index INTEGER NOT NULL DEFAULT 0;
"""


def run() -> None:
    conn = psycopg2.connect(raw_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            print("Adding chunk_index column to document_chunks table …")
            cur.execute(SQL)
            print("Done. Column document_chunks.chunk_index is active.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
