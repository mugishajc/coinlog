from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- users / auth -----------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=120)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must be a 3-letter code")
        return value.upper()


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    currency: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- categories -------------------------------------------------------------

HexColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: HexColor | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: HexColor | None = None


class CategoryOut(ORMModel):
    id: int
    name: str
    color: str | None


# --- expenses ---------------------------------------------------------------


class ExpenseCreate(BaseModel):
    amount: Money
    spent_on: date
    description: str = Field(default="", max_length=255)
    category_id: int | None = None


class ExpenseUpdate(BaseModel):
    amount: Money | None = None
    spent_on: date | None = None
    description: str | None = Field(default=None, max_length=255)
    category_id: int | None = None


class ExpenseOut(ORMModel):
    id: int
    amount: Decimal
    spent_on: date
    description: str
    category_id: int | None
    created_at: datetime


class ExpensePage(BaseModel):
    items: list[ExpenseOut]
    total: int
    limit: int
    offset: int


# --- budgets ----------------------------------------------------------------

Year = Annotated[int, Field(ge=2000, le=2100)]
Month = Annotated[int, Field(ge=1, le=12)]


class BudgetCreate(BaseModel):
    year: Year
    month: Month
    limit: Money
    category_id: int | None = Field(
        default=None, description="Leave empty for an overall monthly budget"
    )


class BudgetUpdate(BaseModel):
    limit: Money


class BudgetOut(ORMModel):
    id: int
    year: int
    month: int
    limit: Decimal
    category_id: int | None
