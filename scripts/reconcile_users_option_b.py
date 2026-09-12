"""Consolidate database identities and apply Option B cleanup.

Actions:
  1. Purge 3 legacy documents for user-123 from MinIO and PostgreSQL.
  2. Purge 7 historical documents for Adam (UUIDs 32f059f7... and 21c87a73...)
     from MinIO and PostgreSQL.
  3. Clean up stale/duplicate records in the users table.
  4. Ensure only official Keycloak accounts exist in users:
     - walid@example.com (e63a8264-e4c7-4581-80a5-298a58ec0e72)
     - adam@example.com (d91f402e-7981-4afe-baf6-fbcf1d396335)
     - admin@doc-intelligence.internal (f1a2b3c4-d5e6-4789-a012-3456789abcde)
  5. Apply UNIQUE constraint on users.email in PostgreSQL.
"""

from sqlalchemy import text
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import (
    DocumentModel,
    DocumentChunkModel,
    ExtractionResultModel,
    ExtractedFieldModel,
    UserModel,
)
from app.composition_root import get_file_storage

OFFICIAL_WALID_ID = "e63a8264-e4c7-4581-80a5-298a58ec0e72"
OFFICIAL_ADAM_ID = "d91f402e-7981-4afe-baf6-fbcf1d396335"
OFFICIAL_ADMIN_ID = "f1a2b3c4-d5e6-4789-a012-3456789abcde"

PURGE_USER_IDS = [
    "user-123",
    "32f059f7-760c-4c05-99a1-485692774198",
    "21c87a73-64cb-4437-b162-669b9f11cdd1",
    "2ee0c660-7500-477c-8497-3299ae18be7b",
]


def execute_option_b_cleanup():
    session = SessionLocal()
    storage = get_file_storage()

    try:
        # 1. Identify documents to purge
        docs_to_purge = (
            session.query(DocumentModel)
            .filter(DocumentModel.user_id.in_(PURGE_USER_IDS))
            .all()
        )
        print(f"Found {len(docs_to_purge)} documents to purge for Option B.")
        purge_doc_ids = [d.id for d in docs_to_purge]

        # 2. Delete from MinIO
        minio_deleted = 0
        for doc in docs_to_purge:
            if doc.storage_path:
                try:
                    storage.delete(doc.storage_path)
                    minio_deleted += 1
                except Exception:
                    pass
        print(f"Deleted {minio_deleted} objects from MinIO.")

        # 3. Delete child and parent rows from PostgreSQL
        if purge_doc_ids:
            chunks_deleted = (
                session.query(DocumentChunkModel)
                .filter(DocumentChunkModel.document_id.in_(purge_doc_ids))
                .delete(synchronize_session=False)
            )
            extractions_deleted = (
                session.query(ExtractionResultModel)
                .filter(ExtractionResultModel.document_id.in_(purge_doc_ids))
                .delete(synchronize_session=False)
            )
            fields_deleted = (
                session.query(ExtractedFieldModel)
                .filter(ExtractedFieldModel.document_id.in_(purge_doc_ids))
                .delete(synchronize_session=False)
            )
            docs_deleted = (
                session.query(DocumentModel)
                .filter(DocumentModel.id.in_(purge_doc_ids))
                .delete(synchronize_session=False)
            )
            print(f"Purged from PostgreSQL: {docs_deleted} docs, {chunks_deleted} chunks, {extractions_deleted} extractions.")

        # 4. Clean up stale/duplicate users in users table
        # Delete purge_user_ids + any leftover test users
        deleted_users = (
            session.query(UserModel)
            .filter(
                (UserModel.id.in_(PURGE_USER_IDS))
                | (UserModel.id.like("user-empty-%"))
                | (UserModel.id.like("user-metrics-%"))
            )
            .delete(synchronize_session=False)
        )
        print(f"Deleted {deleted_users} stale user records.")

        session.commit()

        # 5. Verify and add UNIQUE constraint on users.email
        session.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_email;"))
        session.execute(text("ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email);"))
        session.commit()
        print("Applied UNIQUE (email) constraint on users table.")

        # 6. Verify remaining users and documents
        users = session.query(UserModel).all()
        print(f"\nRemaining users ({len(users)}):")
        for u in users:
            print(f"  id={u.id} email='{u.email}' role={u.role}")

        docs = session.query(DocumentModel).all()
        print(f"\nRemaining documents ({len(docs)}):")
        for d in docs:
            print(f"  id={d.id} user={d.user_id} file='{d.file_name}' v{d.version}")

    except Exception as exc:
        session.rollback()
        print(f"Error during cleanup: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    execute_option_b_cleanup()
