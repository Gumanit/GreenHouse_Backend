from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, Query
from database import get_db

router = APIRouter(
    prefix="/execution_devices",
    tags=["execution_devices"],
)

@router.post("/create")
def create_device(content: schemas.ExecutionDeviceCreate, db: Session = Depends(get_db)):
    return create_device_db(content, db)

@router.get("/read/{id}")
def read_device(id: int, db: Session = Depends(get_db)):
    device = read_device_db(id, db)
    if device is None:
        raise HTTPException(status_code=404, detail="Device doesn't exist")
    return device

@router.get("/read")
def read_devices(skip: int, limit: int, db: Session = Depends(get_db)):
    return read_devices_db(db, skip, limit)

@router.put("/update/{id}")
def update_device(content: schemas.ExecutionDeviceUpdate, id: int, db: Session = Depends(get_db)):
    updated_device = update_device_db(content, id, db)
    if updated_device is None:
        raise HTTPException(status_code=404, detail="Device doesn't exist")
    return updated_device

@router.delete("/delete/{id}")
def delete_device(id: int, db: Session = Depends(get_db)):
    deleted_device = delete_device_db(id, db)
    if deleted_device is None:
        raise HTTPException(status_code=404, detail="Device doesn't exist")
    return {"message": "execution device deleted successfully"}


def create_device_db(content: schemas.ExecutionDeviceCreate, db: Session):
    db_execdev = schemas.ExecutionDevice(**content.model_dump)
    db.add(db_execdev)
    db.commit()
    db.refresh(db_execdev)
    return db_execdev

def read_device_db(id: int, db: Session):
    db_execdev = db.scalars(select(models.ExecutionDevice).where(models.ExecutionDevice.id == id)).first()
    return db_execdev

def read_devices_db(db: Session, skip: int, limit: int):
    return db.scalars(select(models.ExecutionDevice).offset(skip).limit(limit)).all()

def update_device_db(content: schemas.ExecutionDeviceUpdate, id: int, db: Session):
    db_updated = db.scalars(select(models.ExecutionDevice).where(models.ExecutionDevice.id == id)).first()
    if db_updated:
        updated_data = schemas.ExecutionDevice(**content.model_dump(exclude_unset=True))
        for field, value in updated_data.items():
            setattr(db_updated, field, value)
        db.commit()
        db.refresh(db_updated)
    return db_updated

def delete_device_db(id: int, db: Session):
    db_deleted = db.scalars(select(models.ExecutionDevice).where(models.ExecutionDevice.id == id)).first()
    if db_deleted:
        db.delete(db_deleted)
        db.commit()
    return db_deleted