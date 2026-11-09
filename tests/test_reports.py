from datetime import date

import pytest

from app.services.summary import (
    EXCEEDED,
    OK,
    WARNING,
    budget_status,
    month_bounds,
    monthly_trend,
    previous_month,
)


@pytest.mark.parametrize(
    "spent,limit,expected",
    [
        (0, 1000, OK),
        (799, 1000, OK),
        (800, 1000, WARNING),
        (1000, 1000, WARNING),
        (1001, 1000, EXCEEDED),
    ],
)
def test_budget_status(spent, limit, expected):
    assert budget_status(spent, limit, 0.8) == expected


def test_month_helpers():
    assert month_bounds(2028, 2) == (date(2028, 2, 1), date(2028, 2, 29))
    assert previous_month(2026, 1) == (2025, 12)
    assert previous_month(2026, 7) == (2026, 6)


def spend(client, headers, amount, spent_on, category_id=None):
    payload = {"amount": amount, "spent_on": spent_on, "category_id": category_id}
    assert client.post("/expenses", json=payload, headers=headers).status_code == 201


def budget(client, headers, limit, category_id=None, year=2026, month=3):
    payload = {"year": year, "month": month, "limit": limit, "category_id": category_id}
    assert client.post("/budgets", json=payload, headers=headers).status_code == 201


def monthly(client, headers, year=2026, month=3):
    response = client.get(
        "/reports/monthly", params={"year": year, "month": month}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_monthly_summary_totals_and_breakdown(client, auth, category_id):
    spend(client, auth, "10.10", "2026-03-01", category_id)
    spend(client, auth, "20.20", "2026-03-01", category_id)
    spend(client, auth, "5.00", "2026-03-31")
    spend(client, auth, "99.00", "2026-04-01")  # next month, ignored

    summary = monthly(client, auth)

    assert summary["total"] == "35.30"
    assert summary["count"] == 3
    assert [(c["name"], c["spent"], c["count"]) for c in summary["categories"]] == [
        ("Food", "30.30", 2),
        ("Uncategorised", "5.00", 1),
    ]
    assert summary["daily"] == [
        {"day": "2026-03-01", "total": "30.30"},
        {"day": "2026-03-31", "total": "5.00"},
    ]


def test_cents_add_up_exactly(client, auth):
    # 0.1 + 0.2 style sums must not drift.
    for _ in range(10):
        spend(client, auth, "0.10", "2026-03-05")
    spend(client, auth, "0.20", "2026-03-05")
    assert monthly(client, auth)["total"] == "1.20"


def test_change_against_previous_month(client, auth):
    spend(client, auth, "50", "2026-02-10")
    spend(client, auth, "75", "2026-03-10")

    summary = monthly(client, auth)

    assert summary["previous_total"] == "50.00"
    assert summary["change_percent"] == 50.0


def test_no_previous_spending_means_no_change_percent(client, auth):
    spend(client, auth, "75", "2026-03-10")
    assert monthly(client, auth)["change_percent"] is None


def test_budget_alerts_in_summary(client, auth, category_id):
    budget(client, auth, "100")  # overall
    budget(client, auth, "50", category_id)
    spend(client, auth, "45", "2026-03-02", category_id)  # 90% of food budget
    spend(client, auth, "60", "2026-03-03")  # pushes overall to 105

    summary = monthly(client, auth)

    assert summary["overall_budget"]["status"] == "exceeded"
    assert summary["overall_budget"]["remaining"] == "-5.00"
    food = next(c for c in summary["categories"] if c["name"] == "Food")
    assert food["budget"]["status"] == "warning"
    assert food["budget"]["percent_used"] == 90.0
    assert {a["status"] for a in summary["alerts"]} == {"exceeded", "warning"}


def test_budgeted_category_with_no_spending_is_listed(client, auth, category_id):
    budget(client, auth, "50", category_id)
    summary = monthly(client, auth)
    food = next(c for c in summary["categories"] if c["category_id"] == category_id)
    assert food["spent"] == "0.00"
    assert food["budget"]["status"] == "ok"
    assert summary["alerts"] == []


def test_alerts_endpoint_only_returns_problem_budgets(client, auth, category_id):
    budget(client, auth, "1000")
    budget(client, auth, "10", category_id)
    spend(client, auth, "12", "2026-03-04", category_id)

    alerts = client.get("/reports/alerts", params={"year": 2026, "month": 3}, headers=auth).json()

    assert len(alerts) == 1
    assert alerts[0]["category_name"] == "Food"
    assert alerts[0]["status"] == "exceeded"


def test_reports_are_per_user(client, auth, other_auth):
    spend(client, auth, "500", "2026-03-04")
    assert monthly(client, other_auth)["total"] == "0.00"


def test_trend_service_returns_oldest_first(client, auth, db):
    from app.models import User

    spend(client, auth, "10", "2025-12-15")
    spend(client, auth, "30", "2026-02-15")
    user = db.query(User).filter_by(email="amina@example.com").one()

    points = monthly_trend(db, user, 4, today=date(2026, 2, 20))

    assert points == [(2025, 11, 0), (2025, 12, 1000), (2026, 1, 0), (2026, 2, 3000)]


def test_trend_endpoint_validates_range(client, auth):
    assert client.get("/reports/trend", params={"months": 0}, headers=auth).status_code == 422
    assert len(client.get("/reports/trend", params={"months": 3}, headers=auth).json()) == 3
