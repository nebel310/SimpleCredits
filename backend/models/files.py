from datetime import datetime, timezone

from sqlalchemy import ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from database import Model




class FileOrm(Model):
    """Модель файла"""
    __tablename__ = "files"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    object_key: Mapped[str] = mapped_column(nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(nullable=False)
    size: Mapped[int] = mapped_column(nullable=False)
    content_type: Mapped[str | None] = mapped_column(nullable=True)
    extension: Mapped[str | None] = mapped_column(nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )