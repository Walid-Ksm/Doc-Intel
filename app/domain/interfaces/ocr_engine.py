from abc import ABC, abstractmethod


class OCREngineInterface(ABC):
    @abstractmethod
    def extract(self, file_path: str) -> str:
        pass
