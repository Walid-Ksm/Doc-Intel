from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.user_repository import UserRepository
from app.infrastructure.database.document_repository import DocumentRepository
from app.infrastructure.database.extraction_result_repository import (
    ExtractionResultRepository,
)
from app.domain.models.user import User
from app.domain.models.document import Document
from app.domain.models.extraction_result import ExtractionResult

session = SessionLocal()

user_repo = UserRepository(session)
document_repo = DocumentRepository(session)
extraction_repo = ExtractionResultRepository(session)


user = User(id="user-123", email="walid@example.com", role="USER")
user_repo.save(user)


doc = Document(file_name="test.pdf", storage_path="/tmp/test.pdf", user_id=user.id)
document_repo.save(doc)

result1 = ExtractionResult(
    document_id=doc.id, extracted_text="## Texte v1 ##", extraction_method="DOCLING"
)
extraction_repo.save(result1)

result2 = ExtractionResult(
    document_id=doc.id, extracted_text="## Texte v2 ##", extraction_method="DOCLING"
)
extraction_repo.save(result2)


# fetched = document_repo.get_by_id(doc.id)
# print(fetched)

all_results = extraction_repo.list_by_document(doc.id)
for r in all_results:
    print(r)
