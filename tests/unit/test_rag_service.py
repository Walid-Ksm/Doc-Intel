"""Unit tests for RAGService and OllamaClient.

Uses FakeSearchService and FakeLLMClient to verify:
  1. Zero search results short-circuits without invoking the LLM.
  2. Retrieved chunks are correctly formatted into the grounded prompt.
  3. Domain errors (SearchFailedError, LLMGenerationError) propagate properly.
  4. OllamaClient wraps network/timeout failures in LLMGenerationError.

Runs 100% offline with zero external network or GPU dependencies.
"""

import pytest
from typing import List, Optional
from unittest.mock import patch
import httpx

from app.domain.exceptions import LLMGenerationError, SearchFailedError
from app.domain.interfaces.llm_client import LLMClientInterface
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.search_result import SearchResult
from app.infrastructure.llm.ollama_client import OllamaClient
from app.services.rag_service import RAGService, EMPTY_SEARCH_FALLBACK_ANSWER


# ---------------------------------------------------------------------------
# Test Doubles
# ---------------------------------------------------------------------------

class FakeSearchService:
    """In-memory fake for SearchService."""

    def __init__(self, results: Optional[List[SearchResult]] = None, raises: Optional[Exception] = None):
        self._results = results or []
        self._raises = raises
        self.call_count = 0
        self.last_query = None
        self.last_top_k = None
        self.last_user_id = None

    def search(self, query: str, top_k: int, user_id: Optional[str] = None) -> List[SearchResult]:
        self.call_count += 1
        self.last_query = query
        self.last_top_k = top_k
        self.last_user_id = user_id
        if self._raises:
            raise self._raises
        return self._results


class FakeLLMClient(LLMClientInterface):
    """In-memory fake for LLMClientInterface."""

    def __init__(self, response: str = "Fake answer", raises: Optional[Exception] = None):
        self._response = response
        self._raises = raises
        self.call_count = 0
        self.last_prompt = None

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        if self._raises:
            raise self._raises
        return self._response


# ---------------------------------------------------------------------------
# RAGService Tests
# ---------------------------------------------------------------------------

def test_ask_zero_results_short_circuits():
    """When search returns no chunks, LLM must NOT be called."""
    search_service = FakeSearchService(results=[])
    llm_client = FakeLLMClient(response="Should not be generated")
    rag_service = RAGService(search_service=search_service, llm_client=llm_client)

    result = rag_service.ask(question="What is the refund policy?", top_k=5, user_id="user-1")

    assert search_service.call_count == 1
    assert search_service.last_query == "What is the refund policy?"
    assert search_service.last_user_id == "user-1"
    # LLM must NOT have been called
    assert llm_client.call_count == 0
    assert result.answer == EMPTY_SEARCH_FALLBACK_ANSWER
    assert result.sources == []


def test_ask_generates_grounded_answer_with_sources():
    """When chunks are returned, prompt is built with context and LLM is invoked."""
    chunk1 = DocumentChunk(
        id="chunk-1",
        document_id="doc-123",
        chunk_text="Refunds are processed within 14 days of receipt.",
        chunk_index=0,
    )
    chunk2 = DocumentChunk(
        id="chunk-2",
        document_id="doc-123",
        chunk_text="Items must be in original condition for a full refund.",
        chunk_index=1,
    )
    results = [
        SearchResult(chunk=chunk1, similarity_score=0.92, file_name="policy.pdf"),
        SearchResult(chunk=chunk2, similarity_score=0.85, file_name="policy.pdf"),
    ]

    search_service = FakeSearchService(results=results)
    llm_client = FakeLLMClient(response="Refunds take 14 days and items must be in original condition.")
    rag_service = RAGService(search_service=search_service, llm_client=llm_client)

    result = rag_service.ask(question="How do refunds work?", top_k=3, user_id="user-42")

    assert search_service.call_count == 1
    assert llm_client.call_count == 1

    # Verify prompt contains chunks and question
    prompt = llm_client.last_prompt
    assert "Refunds are processed within 14 days" in prompt
    assert "Items must be in original condition" in prompt
    assert "[Document: policy.pdf]" in prompt
    assert "How do refunds work?" in prompt

    # Verify answer and sources
    assert result.answer == "Refunds take 14 days and items must be in original condition."
    assert len(result.sources) == 2
    assert result.sources[0].document_id == "doc-123"
    assert result.sources[0].file_name == "policy.pdf"
    assert result.sources[0].chunk_text == "Refunds are processed within 14 days of receipt."
    assert result.sources[0].similarity_score == 0.92
    assert result.sources[1].chunk_id == "chunk-2"


def test_ask_llm_error_propagates():
    """When LLM generation fails, LLMGenerationError propagates cleanly."""
    chunk = DocumentChunk(
        id="chunk-1",
        document_id="doc-1",
        chunk_text="Some document text",
    )
    results = [SearchResult(chunk=chunk, similarity_score=0.88, file_name="doc.pdf")]

    search_service = FakeSearchService(results=results)
    llm_client = FakeLLMClient(raises=LLMGenerationError(model="gemma3:1b", original_error=RuntimeError("Timeout")))
    rag_service = RAGService(search_service=search_service, llm_client=llm_client)

    with pytest.raises(LLMGenerationError) as exc_info:
        rag_service.ask(question="Query text")

    assert "LLM generation failed" in str(exc_info.value)
    assert exc_info.value.model == "gemma3:1b"


def test_ask_search_error_propagates():
    """When search fails, SearchFailedError propagates without calling LLM."""
    search_service = FakeSearchService(raises=SearchFailedError(query="bad query", original_error=RuntimeError("DB down")))
    llm_client = FakeLLMClient()
    rag_service = RAGService(search_service=search_service, llm_client=llm_client)

    with pytest.raises(SearchFailedError):
        rag_service.ask(question="bad query")

    assert llm_client.call_count == 0


def test_ask_langgraph_with_chat_model():
    """LangGraph RAG pipeline seamlessly invokes LangChain ChatModel objects."""
    from unittest.mock import MagicMock
    from langchain_core.messages import AIMessage

    chunk = DocumentChunk(
        id="chunk-99",
        document_id="doc-99",
        chunk_text="Gemma 3 supports multilingual synthesis.",
    )
    search_service = FakeSearchService(results=[SearchResult(chunk=chunk, similarity_score=0.95, file_name="ai.pdf")])

    from langchain_core.language_models.chat_models import BaseChatModel

    mock_chat_model = MagicMock(spec=BaseChatModel)
    mock_chat_model.invoke.return_value = AIMessage(content="Gemma 3 provides multilingual support.")

    rag_service = RAGService(search_service=search_service, llm_client=mock_chat_model)

    result = rag_service.ask(question="What does Gemma 3 support?")

    assert search_service.call_count == 1
    assert mock_chat_model.invoke.call_count == 1
    assert result.answer == "Gemma 3 provides multilingual support."
    assert len(result.sources) == 1
    assert result.sources[0].document_id == "doc-99"


def test_conversational_intents_intercepted_without_search():
    """Conversational commands like 'you can stop now' bypass vector search entirely."""
    search_service = FakeSearchService(results=[])
    llm_client = FakeLLMClient(response="Fake LLM should not be called")
    rag_service = RAGService(search_service=search_service, llm_client=llm_client)

    # 1. Stop command
    res_stop = rag_service.ask("you can stop now")
    assert "Understood, stopped!" in res_stop.answer
    assert res_stop.sources == []
    assert search_service.call_count == 0
    assert llm_client.call_count == 0

    # 2. Gratitude
    res_thanks = rag_service.ask("thanks a lot!")
    assert "You're welcome!" in res_thanks.answer
    assert res_thanks.sources == []
    assert search_service.call_count == 0

    # 3. Greeting
    res_hello = rag_service.ask("hello")
    assert "Hello!" in res_hello.answer
    assert res_hello.sources == []
    assert search_service.call_count == 0


# ---------------------------------------------------------------------------
# OllamaClient Tests
# ---------------------------------------------------------------------------

def test_ollama_client_success():
    """OllamaClient successfully extracts response from Ollama API payload."""
    client = OllamaClient(base_url="http://localhost:11434", model="gemma3:1b")

    mock_resp = httpx.Response(
        status_code=200,
        json={"model": "gemma3:1b", "response": "Generated RAG response", "done": True},
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )

    with patch("httpx.Client.post", return_value=mock_resp):
        response = client.generate("Test prompt")
        assert response == "Generated RAG response"


def test_ollama_client_connection_error_raises_domain_error():
    """OllamaClient translates network connection errors into LLMGenerationError."""
    client = OllamaClient(base_url="http://localhost:11434", model="gemma3:1b")

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(LLMGenerationError) as exc_info:
            client.generate("Test prompt")

        assert "LLM generation failed for model 'gemma3:1b'" in str(exc_info.value)
        assert isinstance(exc_info.value.original_error, httpx.ConnectError)
