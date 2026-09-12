import os
import sys
from pathlib import Path

# Add project root to sys.path so 'app' can be imported when running script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import DocumentModel, DocumentChunkModel


def main():
    session = SessionLocal()
    try:
        documents = session.query(DocumentModel).all()
        if not documents:
            print("No documents found in the database.")
            return

        print(f"Total documents found: {len(documents)}\n" + "=" * 50)

        for doc in documents:
            chunks = (
                session.query(DocumentChunkModel)
                .filter_by(document_id=doc.id)
                .order_by(DocumentChunkModel.chunk_index.asc())
                .all()
            )

            print(f"\nDocument ID : {doc.id}")
            print(f"File Name   : {doc.file_name}")
            print(f"Status      : {doc.status.value}")
            print(f"Total Chunks: {len(chunks)}")

            if not chunks:
                print("  -> No chunks indexed yet.")
                continue

            indices = [c.chunk_index for c in chunks]
            print(f"  -> chunk_index values: {indices}")

            expected_indices = list(range(len(chunks)))
            if indices == expected_indices:
                print("  -> [PASS] Perfect sequential indices: 0 to", len(chunks) - 1)
            elif all(idx == 0 for idx in indices) and len(chunks) > 1:
                print("  -> [PRE-MIGRATION] All chunks are index 0 (needs re-indexing).")
            else:
                print(f"  -> [WARNING] Non-standard sequence: {indices}")

            # Preview first two chunks
            for c in chunks[:2]:
                print(f"     [Chunk #{c.chunk_index}] ID: {c.id[:8]}... Text: {repr(c.chunk_text[:60])}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
