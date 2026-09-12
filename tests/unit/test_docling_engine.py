import pytest

from app.infrastructure.ocr.docling_engine import DoclingEngine


@pytest.fixture(scope="session")
def docling_engine():
    return DoclingEngine()


@pytest.mark.slow
def test_docling_engine_extracts_content_from_real_pdf(docling_engine):
    result = docling_engine.extract("tests/fixtures/Fiche_PFA.pdf")

    assert isinstance(result, str)
    assert len(result) > 0
    assert "Rapport de recherche" in result
