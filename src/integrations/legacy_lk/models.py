from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, MetaData, String
from sqlalchemy.orm import Mapped, mapped_column, registry

from src.core.config import get_settings

settings = get_settings()
legacy_metadata = MetaData(schema=settings.legacy_db_schema)
legacy_registry = registry(metadata=legacy_metadata)


@legacy_registry.mapped
class LegacyUser:
    """Partial read mapping of Django's auth_user table."""

    __tablename__ = "auth_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    date_joined: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@legacy_registry.mapped
class LegacyClient:
    """Read-only mapping of clients.models.Client; this service does not own it."""

    __tablename__ = "clients_client"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    surname: Mapped[str] = mapped_column(String(100), nullable=False)
    middlename: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bitrix_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{settings.legacy_db_schema}.auth_user.id"),
        nullable=False,
    )
    stage_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
