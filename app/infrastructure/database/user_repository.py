from typing import Optional
from sqlalchemy.orm import Session

from app.domain.interfaces.user_repository import UserRepositoryInterface
from app.domain.models.user import User
from app.infrastructure.database.models import UserModel


class UserRepository(UserRepositoryInterface):
    def __init__(self, session: Session):
        self._session = session

    def save(self, user: User) -> User:
        db_user = UserModel(
            id=user.id,
            email=user.email,
            role=user.role,
        )
        self._session.merge(db_user)
        self._session.commit()
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        db_user = self._session.query(UserModel).filter(UserModel.id == user_id).first()
        if db_user is None:
            return None

        return User(
            id=db_user.id,
            email=db_user.email,
            role=db_user.role,
        )
