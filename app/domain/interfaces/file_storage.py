from abc import ABC, abstractmethod


class FileStorageInterface(ABC):
    @abstractmethod
    def upload(self, file_bytes: bytes, destination_path: str) -> str:
        pass

    @abstractmethod
    def download(self, storage_path: str) -> bytes:
        pass

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        pass
