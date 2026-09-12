class DomainError(Exception):
    pass


class DocumentNotFoundError(DomainError):
    def __init__(self, document_id: str):
        self.document_id = document_id
        super().__init__(f"Document {document_id} not found")


class ExtractionFailedError(DomainError):
    def __init__(self, document_id: str, original_error: Exception):
        self.document_id = document_id
        self.original_error = original_error
        super().__init__(f"Document {document_id} extraction failed: {original_error}")


class IndexingFailedError(DomainError):
    def __init__(self, document_id: str, original_error: Exception):
        self.document_id = document_id
        self.original_error = original_error
        super().__init__(f"Document {document_id} indexing failed: {original_error}")



class StorageError(DomainError):
    def __init__(self, operation: str, storage_path: str, original_error: Exception):
        self.operation = operation
        self.storage_path = storage_path
        self.original_error = original_error
        super().__init__(
            f"Storage {operation} failed for '{storage_path}': {original_error}"
        )


class SearchFailedError(DomainError):
    def __init__(self, query: str, original_error: Exception):
        self.query = query
        self.original_error = original_error
        super().__init__(f"Search failed for query '{query}': {original_error}")


class LLMGenerationError(DomainError):
    def __init__(self, model: str, original_error: Exception):
        self.model = model
        self.original_error = original_error
        super().__init__(f"LLM generation failed for model '{model}': {original_error}")

