from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import SessionLocal, engine, get_db
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import random
from decimal import Decimal
from datetime import datetime
import threading
import time

# Импортируем роутеры
from crud.greenhouses import router as greenhouses_router
from crud.sensors import router as sensors_router
from crud.reports import router as report_router
from simulations import router as simulations_router, lifespan as simulations_lifespan
from crud.agronomic_rules import router as agronomic_rules_router
from crud.execution_devices import router as execution_devices_router
from crud.cameras import router as cameras_router
from init_db import router as admin_router
from crud.users import router as user_router


@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    """Объединенный lifespan менеджер для всех модулей"""

    # Startup логика
    print("Запуск приложения...")

    # Создаем таблицы при старте приложения
    try:
        models.Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы/проверены")

        # Простая проверка без сложных запросов
        db = SessionLocal()
        try:
            print("✅ Подключение к базе данных прошло успешно")
        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")

    # Запускаем lifespan из simulations модуля
    async with simulations_lifespan(app):
        print("✅ Фоновая задача обновления показаний запущена")
        yield


app = FastAPI(
    title="Greenhouse Monitoring API",
    description="API для мониторинга данных теплицы",
    version="1.0.0",
    lifespan=combined_lifespan
)

# Подключаем роутеры
app.include_router(simulations_router)
app.include_router(admin_router)
app.include_router(greenhouses_router)
app.include_router(sensors_router)
app.include_router(report_router)
app.include_router(agronomic_rules_router)
app.include_router(execution_devices_router)
app.include_router(cameras_router)
app.include_router(user_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)