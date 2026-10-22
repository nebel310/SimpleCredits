import os
import uuid
from dotenv import load_dotenv
from typing import AsyncGenerator

from aiobotocore.session import AioSession
from aiobotocore.client import AioBaseClient
from botocore.exceptions import ClientError

from .exceptions import StorageError, ObjectNotFoundError




load_dotenv()

MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "mybucket")

class S3Client:
    """Интерфейс для взаимодействия с s3 хранилищем"""
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = "us-east-1",
    ):
        self.session = AioSession()
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region = region
    
    
    def get_client(self) -> AioBaseClient:
        """Возвращает контекстный менеджер с S3-клиентом"""
        return self.session.create_client(
            's3',
            endpoint_url=self.endpoint,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )
    
    
    async def ensure_bucket(self) -> None:
        """Проверяет существование бакета. Если его нет - создаст"""
        try:
            async with self.get_client() as client:
                await client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get('Code')
            if error_code == "404":
                try:
                    async with self.get_client() as client:
                        await client.create_bucket(Bucket=self.bucket_name)
                except ClientError as creation_error:
                    raise StorageError(
                        f"Не удалось создать бакет: " + str(creation_error)
                    ) from creation_error
        except Exception as e:
            raise StorageError(
                f"Ошибка при работе с хранилищем: " + str(e)
            ) from e
    
    
    async def upload(self, file_data: bytes, file_extension: str | None=None) -> str:
        """Загружает файл в хранилище и возвращает уникальное имя файла в хранилище"""
        file_id = uuid.uuid4().hex
        
        if file_extension:
            object_key = f"{file_id}.{file_extension}"
        else:
            object_key = file_id
        
        try:
            async with self.get_client() as client:
                await client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=file_data
                )
        except ClientError as e:
            raise StorageError(
                f"Ошибка загрузки файла" + str(e)
            ) from e
        
        return object_key

    
    async def download(self, object_key: str) -> bytes:
        """Скачивает файл из MINIO по его имени в хранилище"""
        try:
            async with self.get_client() as client:
                response = await client.get_object(
                    Bucket=self.bucket_name,
                    Key=object_key
                )
                data = await response['Body'].read()
                return data
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == "NoSuchKey":
                raise ObjectNotFoundError(
                    f"Файл с ключём {object_key} не найден в бакете {self.bucket_name}"
                ) from e
            raise StorageError(
                f"Ошибка при скачивании файла {str(e)}"
            ) from e
    
    
    async def download_range_stream(
        self,
        object_key: str,
        start: int | None = None,
        end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Асинхронный генератор чанков файла (весь файл или указанный диапазон)"""
        
        chunk_size = 64 * 1024

        range_header = None
        if start is not None:
            if end is not None:
                range_header = f'bytes={start}-{end}'
            else:
                range_header = f'bytes={start}-'

        try:
            async with self.get_client() as client:
                resp = await client.get_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Range=range_header
                )
                body = resp['Body']
                while True:
                    chunk = await body.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                raise ObjectNotFoundError(f"Файл {object_key} не найден") from e
            if error_code == 'InvalidRange':
                raise StorageError(f"Некорректный диапазон для {object_key}") from e
            raise StorageError(f"Ошибка при скачивании файла: {e}") from e
    
    
    async def delete(self, object_key: str) -> None:
        """Удаляет файл по его ключу"""
        try:
            async with self.get_client() as client:
                await client.delete_object(
                    Bucket=self.bucket_name,
                    Key=object_key
                )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == "NoSuchKey":
                raise ObjectNotFoundError(
                    f"Файл с ключём {object_key} не найден в бакете {self.bucket_name}"
                ) from e
            raise StorageError(
                f"Ошибка при удалении файла: {e}"
            ) from e



s3_client = S3Client(
    MINIO_ENDPOINT,
    MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD,
    MINIO_BUCKET_NAME
)