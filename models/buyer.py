import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from models.address import Address
    from models.cart import Cart
    from models.favorite import Favorite
    from models.notification import Notification
    from models.order import Order
    from models.payment_method import PaymentMethod
    from models.refresh_token import RefreshToken


class Buyer(Base, TimestampMixin):
	__tablename__ = "buyers"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	email: Mapped[str] = mapped_column(
		String(255), nullable=False, unique=True, index=True
	)
	password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
	first_name: Mapped[str] = mapped_column(String(100), nullable=False)
	last_name: Mapped[str] = mapped_column(String(100), nullable=False)
	phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
	avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

	# Relationships
	refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
		back_populates="buyer", cascade="all, delete-orphan"
	)
	addresses: Mapped[list["Address"]] = relationship(
		back_populates="buyer", cascade="all, delete-orphan"
	)
	cart: Mapped["Cart"] = relationship(
		back_populates="buyer", uselist=False, cascade="all, delete-orphan"
	)
	orders: Mapped[list["Order"]] = relationship(back_populates="buyer")
	favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="buyer", cascade="all, delete-orphan"
    )
	notifications: Mapped[list["Notification"]] = relationship(
        back_populates="buyer", cascade="all, delete-orphan"
    )
	payment_methods: Mapped[list["PaymentMethod"]] = relationship(
        back_populates="buyer", cascade="all, delete-orphan"
    )
