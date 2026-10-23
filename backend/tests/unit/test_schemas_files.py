from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas.files import SFileResponse


def test_s_file_response_from_attributes():
    """Собирает SFileResponse из ORM-подобного объекта"""
    obj = SimpleNamespace(
        id=1,
        object_key="abc.png",
        original_name="photo.png",
        size=1024,
        uploaded_by=1,
        content_type="image/png",
        extension="png",
        created_at=datetime.now(timezone.utc),
    )
    assert SFileResponse.model_validate(obj).object_key == "abc.png"


def test_s_file_response_missing_field():
    """Отклоняет объект без обязательных полей"""
    with pytest.raises(ValidationError):
        SFileResponse.model_validate(SimpleNamespace(id=1))