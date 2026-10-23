class StorageError(Exception):
    """Ошибка при взаимодействии с S3-хранилищем (сеть, доступ, 5xx)."""
    pass


class ObjectNotFoundError(Exception):
    """Объект с указанным ключом не найден в бакете."""
    pass