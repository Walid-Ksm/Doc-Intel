import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import io
from app.api.dependencies import get_current_user_id

from app.main import app

client = TestClient(app)


OFFICIAL_USER_ID = "e63a8264-e4c7-4581-80a5-298a58ec0e72"


def test_upload_document_endpoint():
    app.dependency_overrides[get_current_user_id] = lambda: OFFICIAL_USER_ID
    created_doc_id = None

    try:
        fake_pdf_content = b"%PDF-1.4\n%Fake PDF content for testing purposes\n%%EOF"
        fake_file = io.BytesIO(fake_pdf_content)

        files = {"file": ("test_upload.pdf", fake_file, "application/pdf")}

        with patch("app.api.routes.documents.process_document_task.delay") as mock_delay:
            response = client.post("/documents", files=files)

            assert response.status_code == 202

            response_data = response.json()
            assert "document_id" in response_data
            assert response_data["document_id"] is not None
            created_doc_id = response_data["document_id"]
            mock_delay.assert_called_once_with(created_doc_id)
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        if created_doc_id:
            try:
                from app.infrastructure.database.session import SessionLocal
                from app.infrastructure.database.models import DocumentModel
                from app.composition_root import get_file_storage
                session = SessionLocal()
                doc = session.query(DocumentModel).filter_by(id=created_doc_id).first()
                if doc:
                    try:
                        get_file_storage().delete(doc.storage_path)
                    except Exception:
                        pass
                    session.delete(doc)
                    session.commit()
                session.close()
            except Exception:
                pass

