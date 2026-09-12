from abc import ABC, abstractmethod


class LLMClientInterface(ABC):
    """Abstract interface for LLM text generation backends."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text given a prompt.

        Args:
            prompt: The full formatted prompt string.

        Returns:
            The generated raw text response from the model.

        Raises:
            LLMGenerationError: If the model server is unreachable, times out,
                or returns an error response.
        """
        pass
