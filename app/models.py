from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_cents(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).to_integral_value())


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["Budget"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    owner: Mapped[User] = relationship(back_populates="categories")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="category")


class Expense(Base):
    """Amounts are stored as integer cents to keep sums exact."""

    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="ck_expense_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(255), default="")
    spent_on: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="expenses")
    category: Mapped[Category | None] = relationship(back_populates="expenses")

    @property
    def amount(self) -> Decimal:
        return from_cents(self.amount_cents)

    @amount.setter
    def amount(self, value: Decimal) -> None:
        self.amount_cents = to_cents(value)


class Budget(Base):
    """
    A spending limit for one calendar month. With no category it caps total
    spending for the month; with a category it caps just that category.
    """

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", "year", "month", name="uq_budget_period"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_budget_month"),
        CheckConstraint("limit_cents > 0", name="ck_budget_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    limit_cents: Mapped[int] = mapped_column(Integer)

    owner: Mapped[User] = relationship(back_populates="budgets")
    category: Mapped[Category | None] = relationship()

    @property
    def limit(self) -> Decimal:
        return from_cents(self.limit_cents)

    @limit.setter
    def limit(self, value: Decimal) -> None:
        self.limit_cents = to_cents(value)
