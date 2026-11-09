"""Monthly summaries and budget checks. All arithmetic is done in integer cents."""

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Budget, Category, Expense, User, from_cents

OK = "ok"
WARNING = "warning"
EXCEEDED = "exceeded"


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def budget_status(spent_cents: int, limit_cents: int, warning_ratio: float) -> str:
    if spent_cents > limit_cents:
        return EXCEEDED
    if spent_cents >= limit_cents * warning_ratio:
        return WARNING
    return OK


@dataclass
class BudgetCheck:
    budget_id: int
    category_id: int | None
    category_name: str | None
    limit_cents: int
    spent_cents: int
    status: str

    @property
    def limit(self) -> Decimal:
        return from_cents(self.limit_cents)

    @property
    def spent(self) -> Decimal:
        return from_cents(self.spent_cents)

    @property
    def remaining(self) -> Decimal:
        return from_cents(self.limit_cents - self.spent_cents)

    @property
    def percent_used(self) -> float:
        return round(self.spent_cents * 100 / self.limit_cents, 1)


@dataclass
class DayTotal:
    day: date
    total_cents: int

    @property
    def total(self) -> Decimal:
        return from_cents(self.total_cents)


@dataclass
class CategoryLine:
    category_id: int | None
    name: str
    spent_cents: int
    count: int
    budget: BudgetCheck | None = None

    @property
    def spent(self) -> Decimal:
        return from_cents(self.spent_cents)


@dataclass
class MonthlySummary:
    year: int
    month: int
    currency: str
    total_cents: int
    count: int
    previous_total_cents: int
    categories: list[CategoryLine] = field(default_factory=list)
    daily: list[DayTotal] = field(default_factory=list)
    overall_budget: BudgetCheck | None = None
    alerts: list[BudgetCheck] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return from_cents(self.total_cents)

    @property
    def previous_total(self) -> Decimal:
        return from_cents(self.previous_total_cents)

    @property
    def change_percent(self) -> float | None:
        if self.previous_total_cents == 0:
            return None
        delta = self.total_cents - self.previous_total_cents
        return round(delta * 100 / self.previous_total_cents, 1)


def _month_total(db: Session, user_id: int, year: int, month: int) -> int:
    start, end = month_bounds(year, month)
    total = db.scalar(
        select(func.coalesce(func.sum(Expense.amount_cents), 0)).where(
            Expense.user_id == user_id, Expense.spent_on.between(start, end)
        )
    )
    return int(total or 0)


def check_budgets(
    db: Session, user: User, year: int, month: int, warning_ratio: float
) -> list[BudgetCheck]:
    start, end = month_bounds(year, month)
    in_month = (Expense.user_id == user.id, Expense.spent_on.between(start, end))

    by_category = dict(
        db.execute(
            select(Expense.category_id, func.sum(Expense.amount_cents))
            .where(*in_month)
            .group_by(Expense.category_id)
        ).all()
    )
    month_total = sum(by_category.values())

    budgets = db.execute(
        select(Budget, Category.name)
        .outerjoin(Category, Budget.category_id == Category.id)
        .where(Budget.user_id == user.id, Budget.year == year, Budget.month == month)
        .order_by(Budget.category_id.is_not(None), Category.name)
    ).all()

    checks = []
    for budget, category_name in budgets:
        if budget.category_id is None:
            spent = month_total
        else:
            spent = int(by_category.get(budget.category_id, 0))
        checks.append(
            BudgetCheck(
                budget_id=budget.id,
                category_id=budget.category_id,
                category_name=category_name,
                limit_cents=budget.limit_cents,
                spent_cents=spent,
                status=budget_status(spent, budget.limit_cents, warning_ratio),
            )
        )
    return checks


def monthly_summary(
    db: Session, user: User, year: int, month: int, warning_ratio: float
) -> MonthlySummary:
    start, end = month_bounds(year, month)
    in_month = (Expense.user_id == user.id, Expense.spent_on.between(start, end))

    rows = db.execute(
        select(
            Expense.category_id,
            Category.name,
            func.sum(Expense.amount_cents),
            func.count(Expense.id),
        )
        .outerjoin(Category, Expense.category_id == Category.id)
        .where(*in_month)
        .group_by(Expense.category_id, Category.name)
    ).all()

    lines = [
        CategoryLine(
            category_id=category_id,
            name=name or "Uncategorised",
            spent_cents=int(spent),
            count=count,
        )
        for category_id, name, spent, count in rows
    ]

    checks = check_budgets(db, user, year, month, warning_ratio)
    overall = next((c for c in checks if c.category_id is None), None)
    per_category = {c.category_id: c for c in checks if c.category_id is not None}

    for line in lines:
        line.budget = per_category.pop(line.category_id, None)
    # Budgeted categories with nothing spent yet still belong in the summary.
    for check in per_category.values():
        lines.append(
            CategoryLine(
                category_id=check.category_id,
                name=check.category_name or "",
                spent_cents=0,
                count=0,
                budget=check,
            )
        )
    lines.sort(key=lambda line: (-line.spent_cents, line.name))

    daily = db.execute(
        select(Expense.spent_on, func.sum(Expense.amount_cents))
        .where(*in_month)
        .group_by(Expense.spent_on)
        .order_by(Expense.spent_on)
    ).all()

    prev_year, prev_month = previous_month(year, month)
    return MonthlySummary(
        year=year,
        month=month,
        currency=user.currency,
        total_cents=sum(line.spent_cents for line in lines),
        count=sum(line.count for line in lines),
        previous_total_cents=_month_total(db, user.id, prev_year, prev_month),
        categories=lines,
        daily=[DayTotal(day, int(total)) for day, total in daily],
        overall_budget=overall,
        alerts=[c for c in checks if c.status != OK],
    )


def monthly_trend(db: Session, user: User, months: int, today: date) -> list[tuple[int, int, int]]:
    """Totals for the last `months` calendar months, oldest first, as (year, month, cents)."""
    periods = []
    year, month = today.year, today.month
    for _ in range(months):
        periods.append((year, month))
        year, month = previous_month(year, month)
    periods.reverse()
    return [(y, m, _month_total(db, user.id, y, m)) for y, m in periods]
