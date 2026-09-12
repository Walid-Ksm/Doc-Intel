from abc import ABC, abstractmethod
from typing import Optional

from app.domain.models.user import User


class UserRepositoryInterface(ABC):
    @abstractmethod
    def save(self, user: User) -> User:
        pass

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]:
        pass
