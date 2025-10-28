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
from crud.sensorreadings import router as readings_router
from simulations import  router as simulations_router, simulation_running



# Создание таблиц при запуске
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаем таблицы при старте приложения
    try:
        models.Base.metadata.create_all(bind=engine)
        print("Таблицы созданы/проверены")

        # Простая проверка без сложных запросов
        db = SessionLocal()
        try:
            print("Подключение к базе данных прошло успешно")
        finally:
            db.close()

    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")

    yield

    # Останавливаем симуляцию при завершении приложения
    global simulation_running
    simulation_running = False


app = FastAPI(
    title="Greenhouse Monitoring API",
    description="API для мониторинга данных теплицы",
    version="1.0.0",
    lifespan=lifespan
)

# Подключаем роутеры
app.include_router(simulations_router)
app.include_router(greenhouses_router)
app.include_router(sensors_router)
app.include_router(readings_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)