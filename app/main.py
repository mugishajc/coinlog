from fastapi import FastAPI

from .config import get_settings
from .routers import auth, budgets, categories, expenses, reports


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(categories.router)
    app.include_router(expenses.router)
    app.include_router(budgets.router)
    app.include_router(reports.router)
    return app


app = create_app()
