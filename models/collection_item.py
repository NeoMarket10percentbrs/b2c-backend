import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


if TYPE_CHECKING:
    from .collection import Collection

class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "product_id", name="collection_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    collection: Mapped["Collection"] = relationship(
        "Collection", 
        back_populates="items"
    )
