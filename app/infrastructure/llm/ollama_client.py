import os
import httpx
from typing import Optional

from app.domain.exceptions import LLMGenerationError
from app.domain.interfaces.llm_client import LLMClientInterface


class OllamaClient(LLMClientInterface):
    """Client for local Ollama instance generating responses via /api/generate."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:1b")
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """Send a prompt to Ollama /api/generate and return the response text.

        Args:
            prompt: The formatted prompt to send to the model.

        Returns:
            The text response from the model.

        Raises:
            LLMGenerationError: If Ollama is unreachable, times out, or returns an error.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
        except Exception as exc:
            raise LLMGenerationError(model=self.model, original_error=exc) from exc
