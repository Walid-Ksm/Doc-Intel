"""
migrate_hnsw_index.py
─────────────────────
Creates the HNSW approximate nearest-neighbour index on the
`document_chunks.embedding` column for the existing database.

Context
───────
`Base.metadata.create_all()` only adds NEW tables and columns; it never
modifies existing ones or creates missing indexes on already-live tables.
This script must be run once against any database provisioned before the
HNSW __table_args__ entry was added to DocumentChunkModel.

Index parameters
────────────────
  m = 16               — bi-directional links per node (pgvector default).
  ef_construction = 64 — candidate list size at build time.
  vector_cosine_ops    — distance function matching the E5 model family.

Usage
─────
  python scripts/migrate_hnsw_index.py
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Strip the SQLAlchemy dialect prefix — psycopg2 needs a plain DSN.
raw_url = os.getenv("DATABASE_URL", "").replace("postgresql+psycopg2://", "postgresql://")

SQL = """
CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
"""


def run() -> None:
    conn = psycopg2.connect(raw_url)
    # HNSW index creation is DDL and runs outside a transaction block.
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            print("Creating HNSW index on document_chunks.embedding …")
            cur.execute(SQL)
            print("Done. HNSW index ix_document_chunks_embedding_hnsw is active.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
