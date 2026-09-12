from typing import List

from langchain_huggingface import HuggingFaceEmbeddings


class E5EmbeddingsWrapper:
    def __init__(self, model: HuggingFaceEmbeddings) -> None:
        self._model = model
    # embed_passages — used during indexing (this pipeline)
    def embed_passages(self, texts: List[str]) -> List[List[float]]:
        prefixed = [f"passage: {text}" for text in texts]
        return self._model.embed_documents(prefixed)
    # embed_query — used during retrieval (future RAG endpoint)
    def embed_query(self, text: str) -> List[float]:
        return self._model.embed_query(f"query: {text}")
