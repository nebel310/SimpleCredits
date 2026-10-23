from fastapi import APIRouter, Depends, HTTPException

from models.auth import UserOrm
from repositories.auth import UserRepository
from schemas.base import ValidationErrorResponse, ErrorResponse
from schemas.auth import (
    LoginResponse, LogoutResponse, SUserRegister,
    RefreshResponse, RegisterResponse, SUser,
    SUserLogin, SUserUpdate, SUserListResponse
)
from utils.security import create_access_token, get_current_user, oauth2_scheme
from utils.pagination import encode_cursor, decode_cursor
from minio.exceptions import StorageError, ObjectNotFoundError




router = APIRouter(
    prefix="/auth",
    tags=['Пользователи']
)



@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    responses={
        400: {"model": ValidationErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def register_user(user_data: SUserRegister):
    """
    Регистрация нового пользователя.
    
    Пароль и подтверждение пароля должны совпадать.
    Email должен быть уникальным.
    """
    try:
        user_id = await UserRepository.register_user(user_data)
        
        return RegisterResponse(
            success=True,
            user_id=user_id,
            message="Регистрация прошла успешно"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Неверный email или пароль"},
        500: {"model": ErrorResponse}
    }
)
async def login_user(login_data: SUserLogin):
    """
    Вход в систему с получением токенов доступа.
    
    При успехе возвращает access_token и refresh_token.
    Access токен используется для доступа к защищенным эндпоинтам.
    Refresh токен используется для получения нового access токена.
    """
    try:
        user = await UserRepository.authenticate_user(login_data.email, login_data.password)
        
        if not user:
            raise HTTPException(status_code=400, detail="Неверный email или пароль")
        
        access_token = create_access_token(data={"sub": user.email})
        refresh_token = await UserRepository.create_refresh_token(user.id)
        
        return LoginResponse(
            success=True,
            message="Вы вошли в аккаунт",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
        
    except HTTPException:
        raise
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
        )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Неверный refresh токен"},
        500: {"model": ErrorResponse}
    }
)
async def refresh_token(refresh_token: str):
    """
    Обновление access токена с помощью refresh токена.
    
    Refresh токен должен быть валидным и не истекшим.
    Возвращает новый access токен.
    """
    try:
        user = await UserRepository.get_user_by_refresh_token(refresh_token)
        
        if not user:
            raise HTTPException(status_code=400, detail="Неверный refresh токен")
        
        new_access_token = create_access_token(data={"sub": user.email})
        
        return RefreshResponse(
            access_token=new_access_token,
            token_type="bearer"
        )
        
    except HTTPException:
        raise
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        500: {"model": ErrorResponse}
    }
)
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: UserOrm = Depends(get_current_user)
):
    """
    Выход из системы.
    
    Токен добавляется в черный список.
    Refresh токен пользователя отзывается.
    Требует валидный access токен.
    """
    try:
        await UserRepository.add_to_blacklist(token)
        await UserRepository.revoke_refresh_token(current_user.id)
        
        return LogoutResponse(success=True)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
        )


@router.get(
    "/me",
    response_model=SUser,
    responses={
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        500: {"model": ErrorResponse}
    }
)
async def get_current_user_info(current_user: UserOrm = Depends(get_current_user)):
    """
    Получение информации о текущем пользователе.
    
    Возвращает данные пользователя из базы данных.
    Требует валидный access токен.
    """
    try:
        return SUser.model_validate(current_user)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
        )


@router.patch(
    "/me",
    response_model=SUser,
    responses={
        400: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        404: {"model": ErrorResponse, "description": "Файл не найден"},
        500: {"model": ErrorResponse}
    }
)
async def update_current_user(
    update_data: SUserUpdate,
    current_user: UserOrm = Depends(get_current_user)
):
    """
    Обновление данных текущего пользователя.
    Можно передать только те поля, которые требуется изменить.
    """
    # Передаём только те поля, которые не None
    cleaned_data = update_data.model_dump(exclude_none=True)

    try:
        updated_user = await UserRepository.update_user(
            user_id=current_user.id,
            update_data=cleaned_data
        )
        return updated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ObjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except StorageError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка хранилища: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get(
    "/users",
    response_model=SUserListResponse,
    responses={
        400: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        500: {"model": ErrorResponse}
    }
)
async def get_users(
    cursor: str | None = None,
    direction: str = "forward",
    limit: int = 10,
    current_user: UserOrm = Depends(get_current_user)
):
    """Получение списка пользователей с пагинацией (курсорная)."""
    # Валидация limit
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="Лимит должен быть от 1 до 50")
    if direction not in ("forward", "backward"):
        raise HTTPException(status_code=400, detail="Недопустимое направление")
    
    cursor_id = None
    if cursor:
        cursor_id = decode_cursor(cursor)
        if cursor_id is None:
            raise HTTPException(status_code=400, detail="Некорректный курсор")

    try:
        users, next_id, prev_id = await UserRepository.get_users_paginated(
            cursor_id=cursor_id,
            direction=direction,
            limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SUserListResponse(
        users=[SUser.model_validate(u) for u in users],
        next_cursor=encode_cursor(next_id) if next_id else None,
        previous_cursor=encode_cursor(prev_id) if prev_id else None
    )