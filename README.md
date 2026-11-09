# fastapi-expense-tracker

[![CI](https://github.com/mugishajc/fastapi-expense-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/mugishajc/fastapi-expense-tracker/actions/workflows/ci.yml)

A personal expense tracker API. Users sign up, log expenses against their own
categories, set monthly budgets and get a monthly summary that flags budgets
that are close to or over their limit.

## Features

- OAuth2 password flow with JWT bearer tokens. Passwords hashed with bcrypt.
- Categories per user. Six common ones are created at sign-up.
- Expenses with filters (date range, category, uncategorised, amount range,
  text search) and limit/offset pagination.
- Monthly budgets, either overall or per category.
- Reports:
  - monthly summary: total, count, change against last month, spend per
    category with its budget status, daily totals
  - budget alerts: `warning` at 80% of a limit (configurable), `exceeded` above 100%
  - spending trend over the last N months
- Money stored as integer cents, so totals never drift. The API takes and
  returns decimal strings such as `"12.50"`.
- Each user only ever sees their own data. Another user's record returns 404.
- Alembic migrations, checked against the models in CI.

## Stack

Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, pydantic-settings,
Alembic, PyJWT, bcrypt, SQLite. Tests use pytest and FastAPI's TestClient (httpx).

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env      # then set EXPENSES_JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

### Configuration

All settings are read from the environment (or `.env`) with the `EXPENSES_` prefix.

| Variable | Default | Notes |
|----------|---------|-------|
| `EXPENSES_DATABASE_URL` | `sqlite:///./expenses.db` | any SQLAlchemy URL |
| `EXPENSES_JWT_SECRET` | dev placeholder | **must be set outside development** |
| `EXPENSES_ACCESS_TOKEN_MINUTES` | `60` | token lifetime |
| `EXPENSES_BUDGET_WARNING_RATIO` | `0.8` | share of a budget that triggers `warning` |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | create an account |
| POST | `/auth/token` | log in (form fields `username` = email, `password`) |
| GET | `/auth/me` | current user |
| GET/POST | `/categories` | list / create |
| PATCH/DELETE | `/categories/{id}` | rename, recolour, delete (expenses become uncategorised) |
| GET/POST | `/expenses` | list with filters / create |
| GET/PATCH/DELETE | `/expenses/{id}` | |
| GET/POST | `/budgets` | list (filter by `year`, `month`) / create |
| PATCH/DELETE | `/budgets/{id}` | change limit / delete |
| GET | `/reports/monthly?year=&month=` | monthly summary (defaults to this month) |
| GET | `/reports/alerts?year=&month=` | budgets in `warning` or `exceeded` state |
| GET | `/reports/trend?months=6` | totals for the last N months |
| GET | `/health` | liveness check |

Expense list filters: `date_from`, `date_to`, `category_id`, `uncategorized`,
`min_amount`, `max_amount`, `q`, `limit` (max 200), `offset`.

## Example

```bash
curl -X POST localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email": "amina@example.com", "password": "s3cret-pass", "currency": "RWF"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/token \
  -d username=amina@example.com -d password=s3cret-pass | jq -r .access_token)

curl -X POST localhost:8000/budgets -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"year": 2026, "month": 11, "limit": "100000"}'

curl -X POST localhost:8000/expenses -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"amount": "85000", "spent_on": "2026-11-03", "description": "Rent share"}'

curl "localhost:8000/reports/alerts?year=2026&month=11" -H "Authorization: Bearer $TOKEN"
```

```json
[
  {
    "budget_id": 1,
    "category_id": null,
    "category_name": null,
    "limit": "100000.00",
    "spent": "85000.00",
    "remaining": "15000.00",
    "percent_used": 85.0,
    "status": "warning"
  }
]
```

## Tests

```bash
pytest
ruff check . && ruff format --check .
```

Tests run against an in-memory SQLite database and cover auth and tokens,
CRUD and filters, ownership rules, budget rules, the summary maths and the
migrations.

## Project layout

```
app/
  main.py          app factory and router wiring
  config.py        settings
  database.py      engine, session, Base
  models.py        User, Category, Expense, Budget
  schemas.py       request and response models
  security.py      password hashing and JWT
  deps.py          current-user dependency
  routers/         auth, categories, expenses, budgets, reports
  services/summary.py   monthly summary and budget checks
alembic/           migrations
tests/
```

## License

MIT, see [LICENSE](LICENSE).
