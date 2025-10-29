from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, Query
from database import get_db

router = APIRouter(
    prefix="/sensors",
    tags=["sensors"],
)

@router.post("/", response_model=schemas.Sensor)
def create_sensor(sensor: schemas.SensorCreate, db: Session = Depends(get_db)):
    return create_sensor_db(db=db, sensor=sensor)

@router.get("/", response_model=List[schemas.Sensor])
def read_sensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    sensors = get_sensors_db(db, skip=skip, limit=limit)
    return sensors

@router.get("/{sensor_id}", response_model=schemas.Sensor)
def read_sensor(sensor_id: int, db: Session = Depends(get_db)):
    db_sensor = get_sensor_db(db, sensor_id=sensor_id)
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return db_sensor

@router.put("/{sensor_id}", response_model=schemas.SensorUpdate)
def update_sensor(
    sensor_id: int,
    sensor_update: schemas.SensorUpdate,
    db: Session = Depends(get_db)
):
    db_sensor = update_sensor_db(db, sensor_id=sensor_id, sensor_update=sensor_update)
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return db_sensor

@router.delete("/{sensor_id}")
def delete_sensor(sensor_id: int, db: Session = Depends(get_db)):
    db_sensor = delete_sensor_db(db, sensor_id=sensor_id)
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return {"message": "Sensor deleted successfully"}

@router.get("/greenhouse/{greenhouse_id}", response_model=List[schemas.Sensor])
def read_greenhouse_sensors(greenhouse_id: int, db: Session = Depends(get_db)):
    sensors = get_sensors_by_greenhouse_db(db, greenhouse_id=greenhouse_id)
    return sensors

# Функции работы с БД
def get_sensor_db(db: Session, sensor_id: int):
    return db.query(models.Sensor).filter(models.Sensor.sensor_id == sensor_id).first()

def get_sensors_db(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Sensor).offset(skip).limit(limit).all()

def get_sensors_by_greenhouse_db(db: Session, greenhouse_id: int):
    return db.query(models.Sensor).filter(models.Sensor.greenhouse_id == greenhouse_id).all()

def create_sensor_db(db: Session, sensor: schemas.SensorCreate):
    db_sensor = models.Sensor(**sensor.model_dump())
    db.add(db_sensor)
    db.commit()
    db.refresh(db_sensor)
    return db_sensor

def update_sensor_db(db: Session, sensor_id: int, sensor_update: schemas.SensorUpdate):
    db_sensor = db.query(models.Sensor).filter(models.Sensor.sensor_id == sensor_id).first()
    if db_sensor:
        update_data = sensor_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_sensor, field, value)
        db.commit()
        db.refresh(db_sensor)
    return db_sensor

def delete_sensor_db(db: Session, sensor_id: int):
    db_sensor = db.query(models.Sensor).filter(models.Sensor.sensor_id == sensor_id).first()
    if db_sensor:
        db.delete(db_sensor)
        db.commit()
    return db_sensor

def get_sensor_info(db: Session, sensor_id: int) -> Optional[dict]:
    sensor = db.query(models.Sensor).filter(models.Sensor.sensor_id == sensor_id).first()

    if sensor:
        return {
            'sensor_id': sensor.sensor_id,
            'greenhouse_id': sensor.greenhouse_id,
            'type': sensor.type,
        }
    return None

def get_greenhouse_info(db: Session, greenhouse_id: int) -> Optional[dict]:
    greenhouse = db.query(models.Greenhouse).filter(models.Greenhouse.greenhouse_id == greenhouse_id).first()
    if greenhouse:
        return {
            'greenhouse_name': greenhouse.name,
            'greenhouse_id': greenhouse.greenhouse_id,
            'location': greenhouse.location,
            'description': greenhouse.description
        }
    return None