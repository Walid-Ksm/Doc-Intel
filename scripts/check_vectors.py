import os
import sys
from pathlib import Path

# Add project root to sys.path so 'app' can be imported when running script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import DocumentChunkModel
import sys

def check(doc_id: str):
    session = SessionLocal()
    chunks = session.query(DocumentChunkModel).filter_by(document_id=doc_id).all()
    print(f"\nFound {len(chunks)} chunks for document {doc_id}!\n")
    
    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i+1} ---")
        print(f"Metadata: {chunk.metadata_json}")
        print(f"Text Preview: {chunk.chunk_text[:100]}...")
        if chunk.embedding is not None:
            print(f"Vector Dimension: {len(chunk.embedding)}")
            print(f"Vector Preview: {chunk.embedding[:3]} ...")
        else:
            print("Vector: None!")
        print("-" * 30)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide a document ID. Example: python check_vectors.py b5a455eb-0369-4f5c-bd70-a8b857e23d5d")
    else:
        check(sys.argv[1])
