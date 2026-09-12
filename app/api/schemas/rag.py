from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ChatMessageItem(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="Role of the sender")
    content: str = Field(..., description="Message text content")


class RAGAskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question to answer using document context")
    top_k: int = Field(5, ge=1, le=20, description="Number of context chunks to retrieve")
    user_id: Optional[str] = Field(None, description="Optional user ID filter")
    history: List[ChatMessageItem] = Field(default_factory=list, description="Prior conversation messages")


class RAGSourceItem(BaseModel):
    document_id: str
    file_name: str
    chunk_text: str
    similarity_score: float


class RAGAskResponse(BaseModel):
    answer: str
    sources: List[RAGSourceItem]
