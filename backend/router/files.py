import re
from urllib.parse import quote

from fastapi import(
    APIRouter, Depends, HTTPException,
    UploadFile, status, File,
    Form, Response, Request
)
from fastapi.responses import StreamingResponse

from minio.exceptions import StorageError, ObjectNotFoundError
from schemas.base import ErrorResponse, ValidationErrorResponse, SuccessResponse
from schemas.files import SFileResponse
from models.auth import UserOrm
from repositories.files import FileRepository
from utils.security import get_current_user




router = APIRouter(
    prefix="/files",
    tags=['Файлы']
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _safe_filename(name: str) -> str:
    """Имя без кавычек и переводов строк — через имя файла нельзя подставить свой заголовок"""
    return re.sub(r'[\r\n"]', '', name or '') or 'file'


def _content_disposition(name: str) -> str:
    """
    Content-Disposition для любого имени, в том числе кириллического.
    Заголовки HTTP — только latin-1, поэтому имя кладём дважды: латиницей
    для старых клиентов и в filename* (RFC 5987) в UTF-8.
    """
    safe = _safe_filename(name)
    stem, dot, ext = safe.rpartition(".")
    if not dot:
        stem, ext = safe, ""
    to_ascii = lambda v: v.encode("ascii", "ignore").decode().strip()
    ascii_name = (to_ascii(stem) or "file") + (f".{to_ascii(ext)}" if to_ascii(ext) else "")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(safe)}"


async def _get_accessible_file(file_id: int, current_user: UserOrm):
    """
    Возвращает метаданные файла, если он принадлежит пользователю или пользователь — админ.
    Чужой файл выглядит как несуществующий (404), чтобы нельзя было перебирать id.
    """
    file_data = await FileRepository.get_file_info_by_id(file_id)
    if file_data.uploaded_by != current_user.id and current_user.role != "admin":
        raise ObjectNotFoundError(f"Файл с id = {file_id} не найден")
    return file_data



@router.post(
    "/",
    response_model=SFileResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ValidationErrorResponse, "description": "Ошибка валидации"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"},
        502: {"model": ErrorResponse, "description": "Ошибка связи с S3-хранилищем"},
    }
)
async def upload_file(
    file: UploadFile,
    current_user: UserOrm = Depends(get_current_user)
):
    """
    Загружает файл в облачное хранилище
    """
    try:
        file_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Ошибка чтения файла")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Файл пустой")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 10 МБ")

    try:
        file_data = await FileRepository.upload_file(
            file_bytes=file_bytes,
            original_name=file.filename,
            uploaded_by=current_user.id,
        )
        return file_data

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except StorageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get(
    "/{file_id}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Полный файл или часть (если Range)"},
        206: {"description": "Частичное содержимое (Range)"},
        404: {"model": ErrorResponse, "description": "Файл не найден"},
        416: {"model": ErrorResponse, "description": "Невалидный Range"},
        502: {"model": ErrorResponse, "description": "Ошибка хранилища"},
    }
)
async def download_file(
    file_id: int,
    request: Request,
    current_user: UserOrm = Depends(get_current_user)
):
    """Скачивание своего файла целиком или по частям (Range)"""
    try:
        file_info = await _get_accessible_file(file_id, current_user)
    except ObjectNotFoundError:
        raise HTTPException(status_code=404, detail="Файл не найден")

    file_size = file_info.size
    content_type = file_info.content_type or "application/octet-stream"
    safe_filename = _safe_filename(file_info.original_name)

    range_header = request.headers.get("Range")
    if range_header:
        try:
            unit, ranges = range_header.split("=")
            if unit.strip() != "bytes":
                raise ValueError("Неподдерживаемый тип диапазона")
            start_str, end_str = ranges.split("-") if "-" in ranges else (ranges, "")
            start = int(start_str.strip()) if start_str.strip() else 0
            end = int(end_str.strip()) if end_str.strip() else file_size - 1
        except Exception:
            raise HTTPException(status_code=400, detail="Некорректный заголовок Range")

        if start < 0 or end >= file_size or start > end:
            raise HTTPException(
                status_code=416,
                detail="Запрошенный диапазон неудовлетворителен",
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        content_length = end - start + 1
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Disposition": _content_disposition(safe_filename),
        }
        return StreamingResponse(
            FileRepository.stream_file_range(file_id, start, end),
            status_code=206,
            media_type=content_type,
            headers=headers,
        )
    else:
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": _content_disposition(safe_filename),
        }
        return StreamingResponse(
            FileRepository.stream_file_range(file_id),
            status_code=200,
            media_type=content_type,
            headers=headers,
        )


@router.get(
    "/{file_id}/info",
    response_model=SFileResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"},
        404: {"model": ErrorResponse, "description": "Файл не найден"},
        400: {"model": ValidationErrorResponse, "description": "Ошибка валидации"},
    }
)
async def get_file_info(
    file_id: int,
    current_user: UserOrm = Depends(get_current_user)
):
    """Эндпоинт возвращает метаданные файла по его id"""
    
    try:
        return await _get_accessible_file(file_id, current_user)
    except ObjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.delete(
    "/{file_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Файл не найден"},
        502: {"model": ErrorResponse, "description": "Ошибка хранилища"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"}
    }
)
async def delete_file(
    file_id: int,
    current_user: UserOrm = Depends(get_current_user)
):
    """Эндпоинт для удаления файла"""
    
    try:
        await _get_accessible_file(file_id, current_user)
        await FileRepository.delete_file_by_id(file_id)
        
        return SuccessResponse(detail="Файл успешно удалён")
    except ObjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except StorageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


""" 
TODO:

Реализовать эндпоинт по получению всех пользователей с cursor пагинацией
"""