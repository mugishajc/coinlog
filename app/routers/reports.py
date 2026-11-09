from datetime import date

from fastapi import APIRouter, Query

from ..config import get_settings
from ..deps import CurrentUser, DbSession
from ..models import from_cents
from ..schemas import (
    BudgetCheckOut,
    Month,
    MonthlySummaryOut,
    TrendPoint,
    Year,
)
from ..services.summary import check_budgets, monthly_summary, monthly_trend

router = APIRouter(prefix="/reports", tags=["reports"])


def _period(year: int | None, month: int | None) -> tuple[int, int]:
    today = date.today()
    return year or today.year, month or today.month


@router.get("/monthly", response_model=MonthlySummaryOut)
def monthly(
    db: DbSession,
    user: CurrentUser,
    year: Year | None = Query(default=None),
    month: Month | None = Query(default=None),
):
    """Spending for one month by category and day, with budget status. Defaults to now."""
    year, month = _period(year, month)
    summary = monthly_summary(db, user, year, month, get_settings().budget_warning_ratio)
    return MonthlySummaryOut.model_validate(summary)


@router.get("/alerts", response_model=list[BudgetCheckOut])
def alerts(
    db: DbSession,
    user: CurrentUser,
    year: Year | None = Query(default=None),
    month: Month | None = Query(default=None),
):
    """Budgets that are close to their limit (`warning`) or over it (`exceeded`)."""
    year, month = _period(year, month)
    checks = check_budgets(db, user, year, month, get_settings().budget_warning_ratio)
    return [c for c in checks if c.status != "ok"]


@router.get("/trend", response_model=list[TrendPoint])
def trend(db: DbSession, user: CurrentUser, months: int = Query(default=6, ge=1, le=24)):
    """Total spending for each of the last N months, oldest first."""
    points = monthly_trend(db, user, months, date.today())
    return [TrendPoint(year=y, month=m, total=from_cents(cents)) for y, m, cents in points]
