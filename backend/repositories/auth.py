import os

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import delete, select

from database import new_session
from models.auth import BlacklistedTokenOrm, RefreshTokenOrm, UserOrm
from models.files import FileOrm
from schemas.auth import SUserRegister

from minio.client import s3_client
from minio.exceptions import ObjectNotFoundError, StorageError




load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = os.getenv('ALGORITHM')
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS'))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



class UserRepository:
    """Репозиторий для работы с пользователями."""
    @classmethod
    async def register_user(cls, user_data: SUserRegister) -> int:
        """Регистрирует нового пользователя."""
        async with new_session() as session:
            query = select(UserOrm).where(UserOrm.email == user_data.email)
            result = await session.execute(query)
            
            if result.scalars().first():
                raise ValueError("Пользователь с таким email уже существует")
              
            hashed_password = pwd_context.hash(user_data.password)
            
            user = UserOrm(
                username=user_data.username,
                email=user_data.email,
                hashed_password=hashed_password
            )
            
            session.add(user)
            await session.flush()
            await session.commit()
            
            return user.id
    
    
    @classmethod
    async def authenticate_user(cls, email: str, password: str) -> UserOrm | None:
        """Аутентифицирует пользователя по email и паролю."""
        async with new_session() as session:
            query = select(UserOrm).where(UserOrm.email == email)
            result = await session.execute(query)
            user = result.scalars().first()
            
            if not user or not pwd_context.verify(password, user.hashed_password):
                return None
            
            return user
    
    
    @classmethod
    async def get_user_by_email(cls, email: str) -> UserOrm | None:
        """Получает пользователя по email."""
        async with new_session() as session:
            query = select(UserOrm).where(UserOrm.email == email)
            result = await session.execute(query)
            
            return result.scalars().first()
    
    
    @classmethod
    async def get_user_by_id(cls, user_id: int) -> UserOrm | None:
        """Получает пользователя по ID."""
        async with new_session() as session:
            query = select(UserOrm).where(UserOrm.id == user_id)
            result = await session.execute(query)
            
            return result.scalars().first()
    
    
    @classmethod
    async def get_user_by_refresh_token(cls, refresh_token: str) -> UserOrm | None:
        """Получает пользователя по refresh токену."""
        async with new_session() as session:
            query = select(RefreshTokenOrm).where(RefreshTokenOrm.token == refresh_token)
            result = await session.execute(query)
            refresh_token_orm = result.scalars().first()
            
            if not refresh_token_orm or refresh_token_orm.expires_at < datetime.now(timezone.utc):
                return None
            
            return await cls.get_user_by_id(refresh_token_orm.user_id)
    
    
    @classmethod
    async def create_refresh_token(cls, user_id: int) -> str:
        """Создает новый refresh токен для пользователя."""
        async with new_session() as session:
            delete_query = delete(RefreshTokenOrm).where(RefreshTokenOrm.user_id == user_id)
            await session.execute(delete_query)
            
            refresh_token = jwt.encode({"sub": str(user_id)}, SECRET_KEY, algorithm=ALGORITHM)
            expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            
            refresh_token_orm = RefreshTokenOrm(
                user_id=user_id,
                token=refresh_token,
                expires_at=expires_at
            )
            
            session.add(refresh_token_orm)
            await session.commit()
            
            return refresh_token
    
    
    @classmethod
    async def revoke_refresh_token(cls, user_id: int):
        """Отзывает refresh токен пользователя."""
        async with new_session() as session:
            query = delete(RefreshTokenOrm).where(RefreshTokenOrm.user_id == user_id)
            await session.execute(query)
            await session.commit()
    
    
    @classmethod
    async def add_to_blacklist(cls, token: str):
        """Добавляет токен в черный список."""
        async with new_session() as session:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                
            except JWTError:
                return

            blacklisted_token = BlacklistedTokenOrm(
                token=token,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc)
            )
            
            session.add(blacklisted_token)
            await session.commit()
    
    
    @classmethod
    async def update_user(
        cls,
        user_id: int,
        update_data: dict
    ) -> UserOrm:
        """
        Частично обновляет пользователя.
        `update_data` — словарь полей, которые нужно поменять.
        Возвращает обновлённый объект пользователя.
        """
        
        new_avatar_id = update_data.pop('avatar_id', None)

        async with new_session() as session:
            user = await session.get(UserOrm, user_id)
            if not user:
                raise ValueError("Пользователь не найден")

            if new_avatar_id is not None and new_avatar_id != user.avatar_id:
                file_record = await session.get(FileOrm, new_avatar_id)
                if not file_record:
                    raise ObjectNotFoundError(f"Файл с id={new_avatar_id} не найден")
                if file_record.uploaded_by != user_id:
                    raise ValueError("Нельзя использовать чужие файлы для аватарки")

                if user.avatar_id is not None:
                    old_file = await session.get(FileOrm, user.avatar_id)
                    if old_file:
                        await session.delete(old_file)
                        try:
                            await s3_client.delete(old_file.object_key)
                        except (ObjectNotFoundError, StorageError):
                            pass

                user.avatar_id = new_avatar_id

            if update_data:
                for key, value in update_data.items():
                    if hasattr(user, key):
                        setattr(user, key, value)

            if 'email' in update_data:
                existing = await session.execute(
                    select(UserOrm).where(
                        UserOrm.email == update_data['email'], UserOrm.id != user_id
                    )
                )
                if existing.scalars().first():
                    raise ValueError("Пользователь с таким email уже существует")

            await session.commit()
            await session.refresh(user)
            return user


    @classmethod
    async def get_users_paginated(
        cls,
        cursor_id: int | None,
        direction: str,
        limit: int
    ) -> tuple[list[UserOrm], int | None, int | None]:
        """
        Возвращает список пользователей и ID для курсоров next/previous.
        direction: 'forward' (id > cursor) или 'backward' (id < cursor).
        """
        async with new_session() as session:
            if direction == "forward":
                if cursor_id is not None:
                    query = select(UserOrm).where(
                        UserOrm.id > cursor_id
                    ).order_by(UserOrm.id.asc()).limit(limit + 1)
                else:
                    query = select(UserOrm).order_by(UserOrm.id.asc()).limit(limit + 1)
                result = await session.execute(query)
                items = result.scalars().all()
                users = items[:limit]
                next_id = users[-1].id if len(items) > limit else None
                prev_id = users[0].id if cursor_id is not None else None

            elif direction == "backward":
                if cursor_id is not None:
                    query = select(UserOrm).where(
                        UserOrm.id < cursor_id
                    ).order_by(UserOrm.id.desc()).limit(limit + 1)
                else:
                    query = select(UserOrm).order_by(UserOrm.id.desc()).limit(limit + 1)
                result = await session.execute(query)
                items = result.scalars().all()
                items.reverse()
                users = items[:limit]
                next_id = users[-1].id if cursor_id is not None and len(items) > limit else None
                prev_id = users[0].id if len(items) > limit else None
            else:
                raise ValueError("Invalid direction")

            return users, next_id, prev_id