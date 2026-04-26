import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base, TimestampMixin


if TYPE_CHECKING:
    from .collection_item import CollectionItem


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list["CollectionItem"]] = relationship(
        "CollectionItem", 
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="CollectionItem.position",
    )

