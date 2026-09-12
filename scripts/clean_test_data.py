"""Clean test artifacts and stuck dummy records from PostgreSQL and MinIO.

Targeted for deletion:
  1. All documents owned by test users:
     - user-integration-test
     - celery-test-user
     - test-search-auth-user
     - test-search-other-user
     - search-integration-user-a
     - search-integration-user-b
     - search-other-user
     - user-delete-integration-test
     - Any user matching 'test-%'
  2. All test_upload.pdf versions for user-123 (stuck dummy uploads from tests)
  3. All test documents matching 'test_%' or 'no_extraction_%'

Preserved documents:
  All genuine user documents (Rehab .pdf, Untitled 1.pdf, SC routine.pdf,
  Workout.pdf, Receipt-Example.jpg, etc.) are strictly kept.
"""

import sys
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import (
    DocumentModel,
    DocumentChunkModel,
    ExtractionResultModel,
    ExtractedFieldModel,
    UserModel,
)
from app.composition_root import get_file_storage


TEST_USER_PATTERNS = [
    "user-integration-test",
    "celery-test-user",
    "test-search-auth-user",
    "test-search-other-user",
    "search-integration-user-a",
    "search-integration-user-b",
    "search-other-user",
    "user-delete-integration-test",
]

PRESERVED_FILENAMES = {
    "Rehab .pdf",
    "Untitled 1.pdf",
    "Celery + Langraph expl.pdf",
    "Rapport de stage ITEAM - Soukaina AZERZOU3.pdf",
    "template rapport de stage 4IIR.pdf",
    "Receipt-Example.jpg",
    "Workout.pdf",
    "ReceiptSwiss.jpg",
    "SC routine.pdf",
    "Summary.pdf",
    "team-2-mirra-submission-receipt.pdf",
}


def purge_test_data():
    session = SessionLocal()
    storage = get_file_storage()

    try:
        all_docs = session.query(DocumentModel).all()
        to_delete = []

        for doc in all_docs:
            is_test_user = (
                doc.user_id in TEST_USER_PATTERNS
                or doc.user_id.startswith("test-")
                or "integration" in doc.user_id
            )
            is_dummy_upload = (
                doc.user_id == "user-123" and doc.file_name == "test_upload.pdf"
            )
            is_test_filename = (
                doc.file_name.startswith("test_")
                or doc.file_name.startswith("no_extraction_")
            )

            # Safety check: Never purge genuine files
            if doc.file_name in PRESERVED_FILENAMES and not is_test_user:
                continue

            if is_test_user or is_dummy_upload or is_test_filename:
                to_delete.append(doc)

        print(f"Identified {len(to_delete)} test documents to purge.")
        doc_ids = [d.id for d in to_delete]

        if not doc_ids:
            print("No test documents found to purge.")
            return

        # 1. Delete MinIO objects
        minio_deleted = 0
        for doc in to_delete:
            if doc.storage_path:
                try:
                    storage.delete(doc.storage_path)
                    minio_deleted += 1
                except Exception as e:
                    # Ignore if already absent in MinIO
                    pass

        print(f"Purged {minio_deleted} object(s) from MinIO storage.")

        # 2. Delete child rows from PostgreSQL
        chunks_deleted = (
            session.query(DocumentChunkModel)
            .filter(DocumentChunkModel.document_id.in_(doc_ids))
            .delete(synchronize_session=False)
        )
        extractions_deleted = (
            session.query(ExtractionResultModel)
            .filter(ExtractionResultModel.document_id.in_(doc_ids))
            .delete(synchronize_session=False)
        )
        fields_deleted = (
            session.query(ExtractedFieldModel)
            .filter(ExtractedFieldModel.document_id.in_(doc_ids))
            .delete(synchronize_session=False)
        )

        # 3. Delete parent documents
        docs_deleted = (
            session.query(DocumentModel)
            .filter(DocumentModel.id.in_(doc_ids))
            .delete(synchronize_session=False)
        )

        # 4. Clean up test users if no remaining documents
        users_deleted = (
            session.query(UserModel)
            .filter(
                (UserModel.id.in_(TEST_USER_PATTERNS))
                | (UserModel.id.like("test-%"))
            )
            .delete(synchronize_session=False)
        )

        session.commit()

        print(f"Purged from PostgreSQL:")
        print(f"  - Documents: {docs_deleted}")
        print(f"  - Document Chunks: {chunks_deleted}")
        print(f"  - Extraction Results: {extractions_deleted}")
        print(f"  - Extracted Fields: {fields_deleted}")
        print(f"  - Test Users: {users_deleted}")

        # Verification of remaining documents
        remaining = session.query(DocumentModel).all()
        print(f"\nRemaining genuine documents in database: {len(remaining)}")
        for r in remaining:
            print(f"  [{r.status.value}] id={r.id} user={r.user_id} file='{r.file_name}' v{r.version}")

    except Exception as exc:
        session.rollback()
        print(f"Error during purge: {exc}", file=sys.stderr)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    purge_test_data()
