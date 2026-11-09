from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import Category, User
from ..schemas import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


def get_owned_category(db, user: User, category_id: int) -> Category:
    category = db.get(Category, category_id)
    # Someone else's category looks exactly like a missing one.
    if category is None or category.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


def _ensure_unique_name(db, user: User, name: str, exclude_id: int | None = None) -> None:
    query = select(Category.id).where(
        Category.user_id == user.id, func.lower(Category.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if db.scalar(query):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category '{name}' already exists")


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbSession, user: CurrentUser):
    return db.scalars(
        select(Category).where(Category.user_id == user.id).order_by(Category.name)
    ).all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: DbSession, user: CurrentUser):
    name = payload.name.strip()
    _ensure_unique_name(db, user, name)
    category = Category(user_id=user.id, name=name, color=payload.color)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryUpdate, db: DbSession, user: CurrentUser):
    category = get_owned_category(db, user, category_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        _ensure_unique_name(db, user, changes["name"], exclude_id=category.id)
    for field, value in changes.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: DbSession, user: CurrentUser):
    """Expenses in the category are kept and become uncategorised."""
    category = get_owned_category(db, user, category_id)
    for expense in category.expenses:
        expense.category_id = None
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
