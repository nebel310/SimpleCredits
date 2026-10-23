from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field




class SFileResponse(BaseModel):
    """Информация о сохранённом файле"""
    id: int
    object_key: str
    original_name: str
    size: int
    uploaded_by: int
    content_type: str | None
    extension: str | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{
                "id": 1,
                "object_key": "a1b2c3d4e5f6.png",
                "original_name": "фото.png",
                "uploaded_by": 2,
                "size": 204800,
                "content_type": "image/png",
                "extension": "png",
                "created_at": "2024-01-01T12:00:00Z"
            }]
        }
    )