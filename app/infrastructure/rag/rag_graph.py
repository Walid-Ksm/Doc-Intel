import os
import re
from typing import List, Optional, TypedDict, Union
import logging

from langgraph.graph import StateGraph, START, END
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.domain.exceptions import LLMGenerationError
from app.domain.interfaces.llm_client import LLMClientInterface
from app.domain.models.rag_answer import RAGSource
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


def check_conversational_intent(text: str) -> Optional[str]:
    """Detect conversational, control, or greeting inputs that should not trigger document search.

    Prevents queries like 'stop', 'you can stop now', 'thanks', 'hello' from blindly querying
    the vector database and hallucinating document excerpts.
    """
    cleaned = re.sub(r"[^\w\s]", "", text.strip().lower())
    words = cleaned.split()
    if not words:
        return "I'm here to help! Feel free to ask any question about your documents."

    # Stop / termination / cancellation commands
    stop_phrases = {
        "stop", "stop now", "you can stop", "you can stop now", "please stop",
        "cancel", "nevermind", "never mind", "halt", "abort", "quit", "exit",
        "end", "end chat", "pause", "ok stop", "okay stop"
    }
    if cleaned in stop_phrases or (len(words) <= 4 and any(w in ("stop", "cancel", "abort", "halt") for w in words)):
        return "Understood, stopped! Let me know if you need anything else from your documents."

    # Gratitude / acknowledgments
    thanks_phrases = {
        "thank you", "thanks", "thx", "thank you very much", "thanks a lot",
        "merci", "got it", "great thanks", "ok thanks", "okay thanks", "perfect thanks", "sounds good"
    }
    if cleaned in thanks_phrases or (len(words) <= 3 and any(w in ("thanks", "thank", "thx", "merci") for w in words)):
        return "You're welcome! Feel free to ask if you have any more questions about your documents."

    # Greetings
    greetings = {
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening", "bonjour", "salut"
    }
    if cleaned in greetings or (len(words) <= 2 and words[0] in greetings):
        return "Hello! I am your AI Document Assistant. How can I help you with your documents today?"

    return None


RAG_SYSTEM_PROMPT = (
    "You are an expert document assistant. Your task is to provide a comprehensive, clear, and direct "
    "answer to the user's question based strictly on the provided reference context.\n"
    "- If the user asks about a specific document (by name or topic), focus ENTIRELY on that document.\n"
    "- NEVER combine, blend, or confuse information from different documents into a single summary.\n"
    "- When multiple documents are discussed, clearly separate them with distinct headers.\n"
    "- Synthesize the key facts, steps, and instructions from the context into a helpful, well-structured response.\n"
    "- Carefully inspect tables, line items, product catalogs, prices, and quantities in the context.\n"
    "- Be tolerant of minor typos, misspellings, or phrasing variations in the user's question.\n"
    "- Do NOT repeat, rephrase, or echo the user's question.\n"
    "- Answer in the same language as the user's question (e.g., English, French, etc.).\n"
    "- If the context genuinely does not contain enough information to answer the question, clearly state "
    "(in the language of the question) that the provided documents do not contain enough information.\n"
    "- Never extrapolate or invent facts outside the provided context."
)

RAG_USER_PROMPT_TEMPLATE = """### Reference Context:
{chunks_joined}

### Question:
{question}

### Answer:"""

EMPTY_SEARCH_FALLBACK_ANSWER = (
    "I could not find any relevant information in the provided documents to answer this question."
)


class RAGGraphState(TypedDict, total=False):
    question: str
    user_id: Optional[str]
    top_k: int
    chat_history: List[dict]
    sources: List[RAGSource]
    context_text: str
    document_names: List[str]
    targeted_document: Optional[str]
    is_conversational: bool
    answer: str


def build_rag_graph(
    search_service: SearchService,
    llm: Union[BaseChatModel, LLMClientInterface],
):
    """Build and compile a LangGraph StateGraph for the RAG workflow."""

    def retrieve_node(state: RAGGraphState) -> dict:
        question = state.get("question", "").strip()
        top_k = state.get("top_k", 5)
        user_id = state.get("user_id")

        # Fetch broader candidate pool for query analysis
        fetch_limit = max(top_k * 3, 20)
        raw_results = search_service.search(query=question, top_k=fetch_limit, user_id=user_id)

        if not raw_results:
            logger.warning("RAG retrieval found 0 chunks for question: '%s' (user_id=%s)", question, user_id)
            return {"sources": [], "context_text": "", "document_names": [], "targeted_document": None}

        # Check if the question specifically targets a known document
        candidate_file_names = list({r.file_name for r in raw_results})

        def normalize(s: str) -> str:
            return re.sub(r"[^\w]+", " ", s.lower()).strip()

        norm_question = normalize(question)
        targeted_doc = None
        for file_name in candidate_file_names:
            base_name = file_name.rsplit(".", 1)[0]
            norm_file = normalize(file_name)
            norm_base = normalize(base_name)
            if norm_file in norm_question or (len(norm_base) >= 4 and norm_base in norm_question):
                targeted_doc = file_name
                break

        results = []
        if targeted_doc:
            logger.info("Question specifically targets document: '%s'", targeted_doc)
            targeted_candidates = [r for r in raw_results if r.file_name == targeted_doc]

            # If user asks to summarize / overview the document, provide structural leading chunks
            is_summary = any(
                w in norm_question
                for w in ("summarize", "summary", "overview", "resume", "résumé", "what is", "about", "expliquer", "explain")
            )
            if is_summary and hasattr(search_service, "_chunk_repository") and targeted_candidates:
                target_doc_id = targeted_candidates[0].chunk.document_id
                all_chunks = search_service._chunk_repository.list_by_document(target_doc_id)
                if all_chunks:
                    # Chunks 0..5 provide the title page, table of contents, introduction and main overview
                    from app.domain.models.search_result import SearchResult
                    chunk_limit = max(top_k, 6)
                    results = [
                        SearchResult(chunk=c, similarity_score=1.0, file_name=targeted_doc)
                        for c in all_chunks[:chunk_limit]
                    ]

            if not results:
                results = targeted_candidates[:top_k]
        else:
            # General or multi-document question:
            # Only keep candidate chunks whose similarity score is within 0.08 of top score
            top_score = raw_results[0].similarity_score
            relevant_candidates = [
                r for r in raw_results if (top_score - r.similarity_score) <= 0.08
            ]

            # Group candidates by document
            by_doc: dict = {}
            for r in relevant_candidates:
                by_doc.setdefault(r.file_name, []).append(r)

            max_chunks_per_doc = max(len(v) for v in by_doc.values()) if by_doc else 0
            for i in range(max_chunks_per_doc):
                for doc_name, doc_chunks in by_doc.items():
                    if i < len(doc_chunks) and len(results) < top_k:
                        results.append(doc_chunks[i])

        logger.info(
            "RAG retrieved %d chunks across %d documents (targeted=%s) for query '%s'",
            len(results),
            len({r.file_name for r in results}),
            targeted_doc,
            question,
        )

        sources = [
            RAGSource(
                document_id=r.chunk.document_id,
                file_name=r.file_name,
                chunk_text=r.chunk.chunk_text,
                similarity_score=r.similarity_score,
                chunk_id=r.chunk.id,
                chunk_index=r.chunk.chunk_index,
            )
            for r in results
        ]

        # Group chunks by document so the LLM sees clean, isolated document sections
        doc_grouped: dict = {}
        for r in results:
            doc_grouped.setdefault(r.file_name, []).append(r.chunk.chunk_text.strip())

        formatted_docs = []
        for file_name, chunks in doc_grouped.items():
            merged_content = "\n\n".join(chunks)
            formatted_docs.append(f"[Document: {file_name}]\n{merged_content}")

        chunks_joined = "\n\n----------------------------------------\n\n".join(formatted_docs)
        document_names = list(doc_grouped.keys())

        return {
            "sources": sources,
            "context_text": chunks_joined,
            "document_names": document_names,
            "targeted_document": targeted_doc,
        }

    def generate_node(state: RAGGraphState) -> dict:
        question = state.get("question", "").strip()
        context_text = state.get("context_text", "")
        chat_history = state.get("chat_history", [])
        document_names = state.get("document_names", [])
        targeted_doc = state.get("targeted_document")

        # Cap memory to the last 6 messages (3 conversational turns)
        recent_history = chat_history[-6:] if chat_history else []

        doc_instruction = ""
        if targeted_doc:
            doc_instruction = (
                f"### Targeted Document:\n"
                f"The user is specifically asking about: '{targeted_doc}'.\n"
                f"Provide a thorough, comprehensive response based EXCLUSIVELY on '{targeted_doc}'.\n"
                f"Do NOT reference or invent details from any other document.\n\n"
            )
        elif len(document_names) > 1:
            doc_list_str = ", ".join(document_names)
            doc_instruction = (
                f"### Context Documents:\n"
                f"The reference context contains {len(document_names)} unique documents: {doc_list_str}.\n"
                f"Provide a distinct section for EACH document. Do NOT combine facts across different documents.\n\n"
            )

        current_turn_prompt = (
            f"### Reference Context:\n{context_text}\n\n"
            f"{doc_instruction}"
            f"### Question:\n{question}\n\n"
            f"### Answer:"
        )


        try:
            if isinstance(llm, BaseChatModel) or (
                hasattr(llm, "invoke") and callable(getattr(llm, "invoke")) and not isinstance(llm, LLMClientInterface)
            ):
                # Format conversation turns natively as ChatMessage objects for Gemma 3
                messages = [SystemMessage(content=RAG_SYSTEM_PROMPT)]
                for msg in recent_history:
                    content_clean = msg.get("content", "").strip()
                    if not content_clean:
                        continue
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=content_clean))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=content_clean))

                messages.append(HumanMessage(content=current_turn_prompt))
                response = llm.invoke(messages)
                answer_text = str(getattr(response, "content", response)).strip()
            elif isinstance(llm, LLMClientInterface) or (
                hasattr(llm, "generate") and callable(getattr(llm, "generate"))
            ):
                history_lines = []
                for msg in recent_history:
                    speaker = "User" if msg.get("role") == "user" else "Assistant"
                    content_clean = msg.get("content", "").strip()
                    if content_clean:
                        history_lines.append(f"{speaker}: {content_clean}")
                history_section = ""
                if history_lines:
                    history_section = "### Conversation Context:\n" + "\n".join(history_lines) + "\n\n"

                full_prompt = (
                    f"{RAG_SYSTEM_PROMPT}\n\n"
                    f"{history_section}"
                    f"{current_turn_prompt}"
                )
                answer_text = llm.generate(full_prompt).strip()
            else:
                raise ValueError(f"Unsupported LLM provider type: {type(llm)}")

            logger.info("RAG LLM generated response: '%s'", answer_text[:200])
            return {"answer": answer_text}
        except LLMGenerationError:
            raise
        except Exception as exc:
            model_name = getattr(llm, "model", getattr(llm, "model_name", "gemma3"))
            logger.error("LangGraph LLM generation failed: %s", exc, exc_info=True)
            raise LLMGenerationError(model=str(model_name), original_error=exc) from exc

    def router_node(state: RAGGraphState) -> dict:
        question = state.get("question", "").strip()
        conv_response = check_conversational_intent(question)
        if conv_response:
            logger.info("Conversational intent intercepted for query '%s': '%s'", question, conv_response)
            return {"answer": conv_response, "sources": [], "is_conversational": True}
        return {"is_conversational": False}

    def route_start(state: RAGGraphState) -> str:
        if state.get("is_conversational", False):
            return "conversational"
        return "retrieve"

    def conversational_node(state: RAGGraphState) -> dict:
        return {
            "answer": state.get("answer", "Understood, stopped!"),
            "sources": [],
        }

    def fallback_node(state: RAGGraphState) -> dict:
        return {
            "answer": EMPTY_SEARCH_FALLBACK_ANSWER,
            "sources": [],
        }

    def route_after_retrieval(state: RAGGraphState) -> str:
        sources = state.get("sources", [])
        if sources:
            return "generate"
        return "fallback"

    # Build the StateGraph
    workflow = StateGraph(RAGGraphState)

    workflow.add_node("router", router_node)
    workflow.add_node("conversational", conversational_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("fallback", fallback_node)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        route_start,
        {
            "conversational": "conversational",
            "retrieve": "retrieve",
        },
    )
    workflow.add_conditional_edges(
        "retrieve",
        route_after_retrieval,
        {
            "generate": "generate",
            "fallback": "fallback",
        },
    )
    workflow.add_edge("conversational", END)
    workflow.add_edge("generate", END)
    workflow.add_edge("fallback", END)

    return workflow.compile(name="DocIntelligence_RAG")
