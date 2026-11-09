from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import Expense, User, to_cents
from ..schemas import ExpenseCreate, ExpenseOut, ExpensePage, ExpenseUpdate
from .categories import get_owned_category

router = APIRouter(prefix="/expenses", tags=["expenses"])


def get_owned_expense(db, user: User, expense_id: int) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return expense


@router.get("", response_model=ExpensePage)
def list_expenses(
    db: DbSession,
    user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    uncategorized: bool = False,
    min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, max_length=100, description="Search descriptions"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    filters = [Expense.user_id == user.id]
    if date_from:
        filters.append(Expense.spent_on >= date_from)
    if date_to:
        filters.append(Expense.spent_on <= date_to)
    if uncategorized:
        filters.append(Expense.category_id.is_(None))
    elif category_id is not None:
        filters.append(Expense.category_id == category_id)
    if min_amount is not None:
        filters.append(Expense.amount_cents >= to_cents(min_amount))
    if max_amount is not None:
        filters.append(Expense.amount_cents <= to_cents(max_amount))
    if q:
        filters.append(Expense.description.ilike(f"%{q}%"))

    total = db.scalar(select(func.count(Expense.id)).where(*filters)) or 0
    items = db.scalars(
        select(Expense)
        .where(*filters)
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ExpensePage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: DbSession, user: CurrentUser):
    if payload.category_id is not None:
        get_owned_category(db, user, payload.category_id)
    expense = Expense(
        user_id=user.id,
        category_id=payload.category_id,
        description=payload.description,
        spent_on=payload.spent_on,
    )
    expense.amount = payload.amount
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: DbSession, user: CurrentUser):
    return get_owned_expense(db, user, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, payload: ExpenseUpdate, db: DbSession, user: CurrentUser):
    expense = get_owned_expense(db, user, expense_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("category_id") is not None:
        get_owned_category(db, user, changes["category_id"])
    if "amount" in changes:
        amount = changes.pop("amount")
        if amount is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "amount cannot be null")
        expense.amount = amount
    for field, value in changes.items():
        if field in {"spent_on", "description"} and value is None:
            continue
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: DbSession, user: CurrentUser):
    db.delete(get_owned_expense(db, user, expense_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
