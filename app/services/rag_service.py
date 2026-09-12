from typing import Optional, List, Union, Any
from langchain_core.language_models.chat_models import BaseChatModel

from app.domain.interfaces.llm_client import LLMClientInterface
from app.domain.models.rag_answer import RAGAnswer, RAGSource
from app.infrastructure.rag.rag_graph import build_rag_graph, EMPTY_SEARCH_FALLBACK_ANSWER
from app.services.search_service import SearchService


class RAGService:
    """Orchestrates document retrieval and grounded answer generation via LangGraph."""

    def __init__(
        self,
        search_service: SearchService,
        llm_client: Union[BaseChatModel, LLMClientInterface, Any],
    ) -> None:
        self._search_service = search_service
        self._llm_client = llm_client
        self._graph = build_rag_graph(search_service=search_service, llm=llm_client)

    def ask(
        self,
        question: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
        history: Optional[List[dict]] = None,
    ) -> RAGAnswer:
        """Execute the LangGraph RAG workflow to retrieve context and generate an answer.

        Args:
            question: The natural language question to ask.
            top_k: Number of most relevant chunks to retrieve.
            user_id: Optional user identifier to scope document search.
            history: Optional conversation history turns.

        Returns:
            RAGAnswer containing the generated answer and the source chunks used.

        Raises:
            SearchFailedError: If chunk retrieval fails.
            LLMGenerationError: If the LLM call fails or times out.
        """
        initial_state = {
            "question": question,
            "top_k": top_k,
            "user_id": user_id,
            "chat_history": history or [],
        }

        result = self._graph.invoke(initial_state)

        return RAGAnswer(
            answer=result.get("answer", EMPTY_SEARCH_FALLBACK_ANSWER),
            sources=result.get("sources", []),
        )
