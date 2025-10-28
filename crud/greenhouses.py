from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, Query
from database import get_db

router = APIRouter(
    prefix="/greenhouses",
    tags=["greenhouses"],
)

@router.post("/", response_model=schemas.Greenhouse)
def create_greenhouse(greenhouse: schemas.GreenhouseCreate, db: Session = Depends(get_db)):
    return create_greenhouse_db(db=db, greenhouse=greenhouse)

@router.get("/", response_model=List[schemas.Greenhouse])
def read_greenhouses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    greenhouses = get_greenhouses_db(db, skip=skip, limit=limit)
    return greenhouses

@router.get("/{greenhouse_id}", response_model=schemas.Greenhouse)
def read_greenhouse(greenhouse_id: int, db: Session = Depends(get_db)):
    db_greenhouse = get_greenhouse_db(db, greenhouse_id=greenhouse_id)
    if db_greenhouse is None:
        raise HTTPException(status_code=404, detail="Greenhouse not found")
    return db_greenhouse

@router.put("/{greenhouse_id}", response_model=schemas.Greenhouse)
def update_greenhouse(
    greenhouse_id: int,
    greenhouse_update: schemas.GreenhouseUpdate,
    db: Session = Depends(get_db)
):
    db_greenhouse = update_greenhouse_db(db, greenhouse_id=greenhouse_id, greenhouse_update=greenhouse_update)
    if db_greenhouse is None:
        raise HTTPException(status_code=404, detail="Greenhouse not found")
    return db_greenhouse

@router.delete("/{greenhouse_id}")
def delete_greenhouse(greenhouse_id: int, db: Session = Depends(get_db)):
    db_greenhouse = delete_greenhouse_db(db, greenhouse_id=greenhouse_id)
    if db_greenhouse is None:
        raise HTTPException(status_code=404, detail="Greenhouse not found")
    return {"message": "Greenhouse deleted successfully"}

# Функции работы с БД
def get_greenhouse_db(db: Session, greenhouse_id: int):
    return db.query(models.Greenhouse).filter(models.Greenhouse.greenhouse_id == greenhouse_id).first()

def get_greenhouses_db(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Greenhouse).offset(skip).limit(limit).all()

def create_greenhouse_db(db: Session, greenhouse: schemas.GreenhouseCreate):
    db_greenhouse = models.Greenhouse(**greenhouse.model_dump())
    db.add(db_greenhouse)
    db.commit()
    db.refresh(db_greenhouse)
    return db_greenhouse

def update_greenhouse_db(db: Session, greenhouse_id: int, greenhouse_update: schemas.GreenhouseUpdate):
    db_greenhouse = db.query(models.Greenhouse).filter(models.Greenhouse.greenhouse_id == greenhouse_id).first()
    if db_greenhouse:
        update_data = greenhouse_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_greenhouse, field, value)
        db.commit()
        db.refresh(db_greenhouse)
    return db_greenhouse

def delete_greenhouse_db(db: Session, greenhouse_id: int):
    db_greenhouse = db.query(models.Greenhouse).filter(models.Greenhouse.greenhouse_id == greenhouse_id).first()
    if db_greenhouse:
        db.delete(db_greenhouse)
        db.commit()
    return db_greenhouse