from dataclasses import dataclass

from app.domain.models.document_chunk import DocumentChunk


@dataclass
class SearchResult:
    """Domain value object returned by a semantic similarity search.

    Pairs a retrieved chunk with its cosine similarity score and the
    file name of the parent document (fetched via a JOIN in the
    repository so the service layer never has to do a second query).
    """

    chunk: DocumentChunk
    similarity_score: float  # 1.0 − cosine_distance, rounded to 4 dp
    file_name: str
