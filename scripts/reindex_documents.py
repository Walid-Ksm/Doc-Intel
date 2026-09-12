import os
import sys
from pathlib import Path

# Add project root to sys.path so 'app' can be imported when running script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import DocumentModel, DocumentStatusEnum
from app.composition_root import build_vectorization_service


def reindex_all():
    session = SessionLocal()
    try:
        # Find all documents that have already gone through OCR extraction
        docs = (
            session.query(DocumentModel)
            .filter(DocumentModel.status.in_([DocumentStatusEnum.EXTRACTED, DocumentStatusEnum.INDEXED, DocumentStatusEnum.INDEXING]))
            .all()
        )

        if not docs:
            print("No EXTRACTED or INDEXED documents found to re-index.")
            return

        print(f"Found {len(docs)} document(s) to re-index.\n")

        vectorization_service = build_vectorization_service(session)

        for doc in docs:
            print(f"Re-indexing document {doc.id} ({doc.file_name})...")
            try:
                # If status is currently INDEXED, temporarily set to EXTRACTED so index_document runs
                if doc.status != DocumentStatusEnum.EXTRACTED:
                    doc.status = DocumentStatusEnum.EXTRACTED
                    session.commit()

                vectorization_service.index_document(doc.id)
                print(f"  -> [SUCCESS] Re-indexed {doc.id}!")
            except Exception as e:
                print(f"  -> [SKIPPED] Could not re-index {doc.id}: {e}")
                session.rollback()

        print("\nAll eligible documents processed.")
    except Exception as e:
        print(f"\nError during re-indexing: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    reindex_all()
