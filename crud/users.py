from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, status
from database import get_db
import hashlib
import secrets

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


# Простое хеширование пароля без bcrypt (для разработки)
def get_password_hash(password: str) -> str:
    """Хеширование пароля с солью"""
    # Ограничиваем пароль до 50 символов
    password = password[:50]

    # Добавляем соль для безопасности
    salt = "fixed_salt_for_development"
    salted_password = password + salt

    # Используем SHA-256
    return hashlib.sha256(salted_password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return get_password_hash(plain_password) == hashed_password


@router.post("/", response_model=schemas.User, operation_id="create_user")
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Создание пользователя"""
    # Проверяем, существует ли уже пользователь с таким логином
    existing_user = db.scalar(
        select(models.User).where(models.User.login == user.login)
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this login already exists"
        )

    # Хешируем пароль
    user_data = user.model_dump()
    user_data['password'] = get_password_hash(user_data['password'])

    return create_user_db(db, user_data)


@router.get("/{user_id}", response_model=schemas.User, operation_id="get_user")
def read_user(user_id: int, db: Session = Depends(get_db)):
    """Получение пользователя по ID"""
    user = read_user_db(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get("/", response_model=List[schemas.User], operation_id="list_users")
def read_users(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """Получение списка пользователей"""
    return read_users_db(db, skip, limit)


@router.put("/{user_id}", response_model=schemas.User, operation_id="update_user")
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db)
):
    """Обновление пользователя (включая пароль)"""
    user = update_user_db(db, user_update, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.delete("/{user_id}", operation_id="delete_user")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Удаление пользователя"""
    user = delete_user_db(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return {"message": "User deleted successfully"}


# CRUD функции
def create_user_db(db: Session, user_data: dict) -> models.User:
    """Создание пользователя в БД"""
    created_user = models.User(**user_data)
    db.add(created_user)
    db.commit()
    db.refresh(created_user)
    return created_user


def read_user_db(db: Session, user_id: int) -> Optional[models.User]:
    """Чтение пользователя по ID из БД"""
    return db.scalar(
        select(models.User).where(models.User.id == user_id)
    )


def read_users_db(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    """Чтение списка пользователей из БД"""
    return db.scalars(
        select(models.User)
        .order_by(models.User.id)
        .offset(skip)
        .limit(limit)
    ).all()


def update_user_db(
        db: Session,
        user_update: schemas.UserUpdate,
        user_id: int
) -> Optional[models.User]:
    """Обновление пользователя в БД"""
    user = read_user_db(db, user_id)
    if user:
        update_data = user_update.model_dump(exclude_unset=True)

        # Если обновляется пароль - хешируем его
        if 'password' in update_data and update_data['password']:
            update_data['password'] = get_password_hash(update_data['password'])

        # Обновляем поля
        for field, value in update_data.items():
            setattr(user, field, value)

        db.commit()
        db.refresh(user)
    return user


def delete_user_db(db: Session, user_id: int) -> Optional[models.User]:
    """Удаление пользователя из БД"""
    user = read_user_db(db, user_id)
    if user:
        db.delete(user)
        db.commit()
    return user