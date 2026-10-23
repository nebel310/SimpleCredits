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
        500: {"model": ValidationErrorResponse, "description": "Внутренняя ошибка сервера"},
        404: {"model": ErrorResponse, "description": "Файл не найден"},
        502: {"model": ErrorResponse, "description": "Ошибка хранилища"},
    }
)
async def old_dowload_file(
    file_id: int,
    current_user: UserOrm = Depends(get_current_user)
):
    """Эндпоинт для тупого скачивания файла по его file_id"""
    try:
        file_bytes, file_data = await FileRepository.download_file_by_id(file_id)
        
        safe_filename = file_data.original_name.replace('"', '')
        
        headers = {
            "Content-Disposition": f'attachment; filename="{safe_filename}"'
        }
        return Response(
            content=file_bytes,
            media_type=file_data.content_type or "application/octet-stream",
            headers=headers,
        )
    except ObjectNotFoundError:
        raise HTTPException(status_code=404, detail="Файл не найден")
    except StorageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
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
    """Скачивание файла чанками (Range)"""
    try:
        file_info = await FileRepository.get_file_info_by_id(file_id)
    except ObjectNotFoundError:
        raise HTTPException(status_code=404, detail="Файл не найден")

    file_size = file_info.size
    content_type = file_info.content_type or "application/octet-stream"
    safe_filename = file_info.original_name.replace('"', '')

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
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
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
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
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
        file_data = await FileRepository.get_file_info_by_id(file_id)
        
        return file_data
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