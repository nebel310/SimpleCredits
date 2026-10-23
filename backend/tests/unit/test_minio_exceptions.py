import pytest

from minio.exceptions import ObjectNotFoundError, StorageError


def test_storage_error_is_exception():
    """StorageError наследуется от Exception"""
    assert issubclass(StorageError, Exception)


def test_object_not_found_is_exception():
    """ObjectNotFoundError наследуется от Exception"""
    assert issubclass(ObjectNotFoundError, Exception)


def test_storage_error_raised():
    """StorageError можно поднять с сообщением"""
    with pytest.raises(StorageError, match="boom"):
        raise StorageError("boom")


def test_object_not_found_raised():
    """ObjectNotFoundError можно поднять с сообщением"""
    with pytest.raises(ObjectNotFoundError, match="missing"):
        raise ObjectNotFoundError("missing")