import asyncio
import magic
import mimetypes
from typing import AsyncGenerator

from sqlalchemy import select, delete

from database import new_session
from models.files import FileOrm

from minio.client import s3_client
from minio.exceptions import ObjectNotFoundError, StorageError




class FileRepository:
    """Репозиторий для работы с файлами"""
    
    @staticmethod
    def _get_content_type(file_bytes: bytes) -> str:
        """Возвращает MIME-тип, определённый по сигнатуре файла"""
        try:
            return magic.from_buffer(file_bytes, mime=True)
        except magic.MagicException as e:
            raise ValueError(f"Не удалось определить MIME-тип: {e}")
        
    
    @staticmethod
    def _get_extension(file_bytes: bytes) -> str:
        """Возвращает расширение файла без точки на основе содержимого"""
        mime_type = FileRepository._get_content_type(file_bytes)
        ext = mimetypes.guess_extension(mime_type)
        if ext:
            ext = ext.lstrip('.')
            corrections = {'jpe': 'jpg', 'jpeg': 'jpg', 'svg+xml': 'svg'}
            return corrections.get(ext, ext)

        fallback = mime_type.split('/')[-1]
        fallback_map = {
            'jpeg': 'jpg',
            'svg+xml': 'svg',
            'quicktime': 'mov',
            'x-msvideo': 'avi'
        }
        return fallback_map.get(fallback, fallback)
    
    
    @classmethod
    async def upload_file(
        cls,
        file_bytes: bytes, original_name: str,
        uploaded_by: int
    )-> FileOrm:
        """Метод который сохраняет файл и возвращает объект FileOrm"""
        
        content_type = await asyncio.to_thread(cls._get_content_type, file_bytes)
        extension = await asyncio.to_thread(cls._get_extension, file_bytes)
        
        object_key = await s3_client.upload(file_bytes, extension)
        
        async with new_session() as session:
            file_to_insert = FileOrm(
                object_key = object_key,
                original_name = original_name,
                size = len(file_bytes),
                content_type = content_type,
                extension = extension,
                uploaded_by = uploaded_by
            )
            
            session.add(file_to_insert)
            try:
                await session.commit()
                await session.refresh(file_to_insert)
            except Exception:
                await session.rollback()
                try:
                    await s3_client.delete(object_key)
                except Exception:
                    pass
                raise
        
        return file_to_insert
    
    
    @classmethod
    async def download_file_by_id(
        cls,
        file_id: int
    ) -> tuple[bytes, FileOrm]:
        """
        Скачивает файл по id записи и возвращает его содержимое вместе с метаданными
        Если запись в БД существует, но объекта в MinIO нет – запись удаляется
        """
        async with new_session() as session:
            query = select(FileOrm).where(FileOrm.id == file_id)
            result = await session.execute(query)
            file_data = result.scalars().first()

            if not file_data:
                raise ObjectNotFoundError(f"Файл с id={file_id} не найден в БД")

            object_key = file_data.object_key

        try:
            file_bytes = await s3_client.download(object_key)
        except ObjectNotFoundError:
            async with new_session() as session:
                await session.delete(file_data)
                await session.commit()
            raise ObjectNotFoundError(
                f"Файл с ключом {object_key} отсутствует в хранилище, запись удалена"
            )
        except Exception as e:
            raise StorageError(f"Ошибка при скачивании файла: {e}") from e

        return file_bytes, file_data


    @classmethod
    async def stream_file_range(
        cls,
        file_id: int,
        start: int | None = None,
        end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Возвращает async-генератор чанков файла (весь файл или диапазон)"""
        async with new_session() as session:
            query = select(FileOrm.object_key).where(FileOrm.id == file_id)
            result = await session.execute(query)
            object_key = result.scalar_one_or_none()

        if not object_key:
            raise ObjectNotFoundError(f"Файл с id={file_id} не найден в БД")

        async for chunk in s3_client.download_range_stream(object_key, start, end):
            yield chunk
    
    
    @classmethod
    async def get_file_info_by_id(
        cls,
        file_id: int
    ) -> FileOrm:
        """Метод который возвращает чисто метаданные файла по его id"""
        
        async with new_session() as session:
            query = select(FileOrm).where(FileOrm.id == file_id)
            result = await session.execute(query)
            file_data = result.scalars().first()
            
            if not file_data:
                raise ObjectNotFoundError(f"Файл с id = {file_id} не найден в БД")
            
            return file_data
    
    
    @classmethod
    async def delete_file_by_id(
        cls,
        file_id: int
    ) -> None:
        """Удаляет файл по его id"""
        
        async with new_session() as session:
            query = select(FileOrm).where(FileOrm.id == file_id)
            result = await session.execute(query)
            file_data = result.scalars().first()
            if not file_data:
                raise ObjectNotFoundError(f"Файл с id={file_id} не найден")
            object_key = file_data.object_key

            try:
                await s3_client.delete(object_key)
            except ObjectNotFoundError:
                pass
            except Exception as e:
                raise StorageError(f"Не удалось удалить объект MinIO: {e}") from e

            await session.delete(file_data)
            await session.commit()