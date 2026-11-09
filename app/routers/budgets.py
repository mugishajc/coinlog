from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import Budget, User
from ..schemas import BudgetCreate, BudgetOut, BudgetUpdate, Month, Year
from .categories import get_owned_category

router = APIRouter(prefix="/budgets", tags=["budgets"])


def get_owned_budget(db, user: User, budget_id: int) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None or budget.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Budget not found")
    return budget


@router.get("", response_model=list[BudgetOut])
def list_budgets(
    db: DbSession,
    user: CurrentUser,
    year: Year | None = Query(default=None),
    month: Month | None = Query(default=None),
):
    query = select(Budget).where(Budget.user_id == user.id)
    if year is not None:
        query = query.where(Budget.year == year)
    if month is not None:
        query = query.where(Budget.month == month)
    return db.scalars(query.order_by(Budget.year, Budget.month, Budget.category_id)).all()


@router.post("", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
def create_budget(payload: BudgetCreate, db: DbSession, user: CurrentUser):
    if payload.category_id is not None:
        get_owned_category(db, user, payload.category_id)

    # Checked here as well as by the unique constraint: SQLite treats NULL category ids as
    # distinct, so the unique constraint alone would allow two overall budgets.
    duplicate = db.scalar(
        select(Budget.id).where(
            Budget.user_id == user.id,
            Budget.year == payload.year,
            Budget.month == payload.month,
            Budget.category_id.is_(None)
            if payload.category_id is None
            else Budget.category_id == payload.category_id,
        )
    )
    if duplicate:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A budget for that month and category already exists"
        )

    budget = Budget(
        user_id=user.id, category_id=payload.category_id, year=payload.year, month=payload.month
    )
    budget.limit = payload.limit
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.patch("/{budget_id}", response_model=BudgetOut)
def update_budget(budget_id: int, payload: BudgetUpdate, db: DbSession, user: CurrentUser):
    budget = get_owned_budget(db, user, budget_id)
    budget.limit = payload.limit
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: int, db: DbSession, user: CurrentUser):
    db.delete(get_owned_budget(db, user, budget_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
