from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, Query
from database import get_db

# Создаём маршрутизатор для показаний датчиков
router = APIRouter(
    prefix="/readings",
    tags=["sensor_readings"],
)

@router.post("/", response_model=schemas.SensorReading)
def create_reading(reading: schemas.SensorReadingCreate, db: Session = Depends(get_db)):
    """Создание нового показания"""
    return create_sensor_reading_db(db=db, reading=reading)

@router.get("/", response_model=List[schemas.SensorReading])
def read_readings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получение списка показаний"""
    readings = get_sensor_readings_db(db, skip=skip, limit=limit)
    return readings

@router.get("/{reading_id}", response_model=schemas.SensorReading)
def read_reading(reading_id: int, db: Session = Depends(get_db)):
    """Получение показания по ID"""
    db_reading = get_sensor_reading_db(db, reading_id=reading_id)
    if db_reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    return db_reading

@router.delete("/{reading_id}")
def delete_reading(reading_id: int, db: Session = Depends(get_db)):
    """Удаление показания по ID"""
    db_reading = delete_sensor_reading_db(db, reading_id=reading_id)
    if db_reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    return {"message": "Reading deleted successfully"}

@router.get("/sensor/{sensor_id}", response_model=List[schemas.SensorReading])
def read_sensor_readings(
    sensor_id: int,
    hours: Optional[int] = Query(None, description="Filter by last N hours"),
    db: Session = Depends(get_db)
):
    """Получение показаний конкретного датчика"""
    return get_readings_by_sensor_db(db, sensor_id=sensor_id, hours=hours)

@router.get("/latest/", response_model=List[schemas.SensorReading])
def get_latest_readings(db: Session = Depends(get_db)):
    """Получение последних показаний каждого датчика"""
    return get_latest_readings_db(db)

@router.get("/sensor/{sensor_id}/statistics/")
def get_sensor_statistics(
    sensor_id: int,
    hours: int = Query(24, description="Period for statistics in hours"),
    db: Session = Depends(get_db)
):
    """Получение статистики по датчику"""
    return get_sensor_statistics_db(db, sensor_id=sensor_id, hours=hours)

@router.delete("/")
def delete_all_readings(db: Session = Depends(get_db)):
    """Очистка всех показаний"""
    deleted_count = delete_all_readings_db(db)
    return {
        "message": "All readings deleted",
        "deleted_count": deleted_count
    }

# Функции работы с БД
def get_sensor_reading_db(db: Session, reading_id: int):
    return db.query(models.SensorReading).filter(models.SensorReading.reading_id == reading_id).first()

def get_sensor_readings_db(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.SensorReading).order_by(desc(models.SensorReading.reading_time)).offset(skip).limit(limit).all()

def get_readings_by_sensor_db(db: Session, sensor_id: int, hours: Optional[int] = None):
    query = db.query(models.SensorReading).filter(models.SensorReading.sensor_id == sensor_id)

    if hours:
        time_threshold = datetime.now() - timedelta(hours=hours)
        query = query.filter(models.SensorReading.reading_time >= time_threshold)

    return query.order_by(desc(models.SensorReading.reading_time)).all()

def create_sensor_reading_db(db: Session, reading: schemas.SensorReadingCreate):
    db_reading = models.SensorReading(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading

def get_latest_readings_db(db: Session):
    subquery = db.query(
        models.SensorReading.sensor_id,
        func.max(models.SensorReading.reading_time).label('max_time')
    ).group_by(models.SensorReading.sensor_id).subquery()

    latest_readings = db.query(models.SensorReading).join(
        subquery,
        (models.SensorReading.sensor_id == subquery.c.sensor_id) &
        (models.SensorReading.reading_time == subquery.c.max_time)
    ).all()

    return latest_readings

def get_sensor_statistics_db(db: Session, sensor_id: int, hours: int = 24):
    time_threshold = datetime.now() - timedelta(hours=hours)

    stats = db.query(
        func.count(models.SensorReading.reading_id).label('count'),
        func.avg(models.SensorReading.value).label('avg'),
        func.min(models.SensorReading.value).label('min'),
        func.max(models.SensorReading.value).label('max')
    ).filter(
        models.SensorReading.sensor_id == sensor_id,
        models.SensorReading.reading_time >= time_threshold
    ).first()

    return {
        'sensor_id': sensor_id,
        'period_hours': hours,
        'readings_count': stats.count,
        'average_value': float(stats.avg) if stats.avg else None,
        'min_value': float(stats.min) if stats.min else None,
        'max_value': float(stats.max) if stats.max else None
    }

def delete_sensor_reading_db(db: Session, reading_id: int):
    db_reading = db.query(models.SensorReading).filter(models.SensorReading.reading_id == reading_id).first()
    if db_reading:
        db.delete(db_reading)
        db.commit()
    return db_reading

def delete_all_readings_db(db: Session):
    deleted_count = db.query(models.SensorReading).delete()
    db.commit()
    return deleted_count