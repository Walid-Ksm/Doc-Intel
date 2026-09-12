import logging
from typing import List

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from transformers import AutoTokenizer

from app.domain.interfaces.text_splitter import TextSplitterInterface
from app.domain.models.document_chunk import DocumentChunk
from app.infrastructure.langchain.e5_embeddings import E5EmbeddingsWrapper

logger = logging.getLogger(__name__)

# Headers that Docling uses in its Markdown output.
_HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

# chunk_size=480 *tokens* strictly enforces the 512-token limit of
# intfloat/multilingual-e5-small, leaving a 32-token buffer for the
# "passage: " / "query: " prefix and BERT special tokens ([CLS], [SEP]).
# chunk_overlap=50 preserves a small amount of context across boundaries
# without consuming excessive token budget.
_CHUNK_SIZE_TOKENS = 480
_CHUNK_OVERLAP_TOKENS = 50
_E5_MODEL_NAME = "intfloat/multilingual-e5-small"


class LangChainMarkdownSplitter(TextSplitterInterface):

    def __init__(
        self,
        embedder: E5EmbeddingsWrapper,
        model_name: str = _E5_MODEL_NAME,
    ) -> None:
        self._embedder = embedder
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=_HEADERS_TO_SPLIT_ON,
            strip_headers=False,  # keep headers in chunk text for context
        )
        # Load the model's own tokenizer so that chunk_size is measured in
        # actual tokens rather than characters — the only safe unit for
        # a model with a hard 512-token context window.
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._token_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
            _tokenizer,
            chunk_size=_CHUNK_SIZE_TOKENS,
            chunk_overlap=_CHUNK_OVERLAP_TOKENS,
        )

    def split_and_embed(self, document_id: str, markdown_text: str) -> List[DocumentChunk]:
        # Stage 1: split on Markdown headers
        header_chunks = self._header_splitter.split_text(markdown_text)

        # Stage 2: further split any oversized sections using the
        # tokenizer-aware splitter so the 512-token model limit is
        # enforced precisely rather than approximated by character count.
        fine_chunks = self._token_splitter.split_documents(header_chunks)

        # Filter out empty or whitespace-only chunks that MarkdownHeaderTextSplitter
        # can produce for sections with no body text (e.g. a heading with no content).
        non_empty = [doc for doc in fine_chunks if doc.page_content.strip()]

        if not non_empty:
            logger.warning(
                "split_and_embed produced 0 non-empty chunks for document %s. "
                "The extracted text may be empty or contain only headers.",
                document_id,
            )
            return []

        # Build domain objects before embedding so we have one clean list to work with
        chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                chunk_text=doc.page_content,
                metadata=doc.metadata,
            )
            for i, doc in enumerate(non_empty)
        ]

        # Embed all passages in a single batch call.
        # embed_passages() prepends "passage: " internally — we never do it here.
        logger.info("Embedding %d chunks for document %s.", len(chunks), document_id)
        vectors = self._embedder.embed_passages([chunk.chunk_text for chunk in chunks])

        for chunk, vector in zip(chunks, vectors):
            chunk.attach_embedding(vector)

        return chunks
