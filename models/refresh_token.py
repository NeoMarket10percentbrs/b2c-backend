import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from core.database import Base

if TYPE_CHECKING:
	from models.buyer import Buyer


class RefreshToken(Base):
	__tablename__ = "refresh_tokens"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	buyer_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("buyers.id", ondelete="CASCADE"),
		nullable=False, index=True
	)
	token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
	expires_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False
	)
	revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=func.now(), nullable=False
	)

	# Relationships
	buyer: Mapped["Buyer"] = relationship(back_populates="refresh_tokens")
