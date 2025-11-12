import json

from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, Query
from database import get_db
from models import AgronomicRule

router = APIRouter(
    prefix="/agronomic_rules",
    tags=["agronomic_rules"],
)

@router.post("/create_agronomic_rules", response_model=schemas.AgronomicRule)
def create_agronomic_rule(new_agronomic_rule: schemas.AgronomicRuleCreate, db: Session = Depends(get_db)):
     return create_agrorules_db(db, new_agronomic_rule)

@router.get("/get_agronomic_rule/{agrorule_id}", response_model=schemas.AgronomicRule)
def get_agrorule(agrorule_id: int, db: Session = Depends(get_db)):
    db_agrorule = get_agrorule_db(db, agrorule_id)
    if db_agrorule is None:
        raise HTTPException(status_code=404, detail="Agronomic rule doesn't exist")
    return db_agrorule

@router.get("/get_agronomic_rules", response_model=List[schemas.AgronomicRule])
def get_agrorules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    return get_agrorules_db(db, skip, limit)

@router.put("/update/{agrorule_id}", response_model=schemas.AgronomicRule)
def update_agrorule(agrorule_id: int, updated_rule: schemas.AgronomicRuleUpdate, db: Session = Depends(get_db)):
    updated_rule_db = update_agrorule_db(db, agrorule_id, updated_rule)
    if updated_rule_db is None:
        raise HTTPException(status_code=404, detail="Agronomic rule doesn't exist")
    return updated_rule_db

@router.delete("/delete/{agrorule_id}", status_code=200)
def delete_agrorule(agrorule_id: int, db: Session = Depends(get_db)):
    deleted_rule = delete_agrorule_db(db, agrorule_id)
    if deleted_rule is None:
        raise HTTPException(status_code=404, detail="Agronomic rule doesn't exist")
    return {"message": "Agronomic rule deleted successfully"}

def create_agrorules_db(db: Session, agrorules: schemas.AgronomicRuleCreate):
    agrorules_dict = agrorules.model_dump()
    agrorules_dict["rule_params"] = json.dumps(agrorules_dict["rule_params"])  # ← строка!
    db_agrorules = models.AgronomicRule(**agrorules_dict)
    db.add(db_agrorules)
    db.commit()
    db.refresh(db_agrorules)
    return db_agrorules

def get_agrorule_db(db: Session, agrorule_id: int):
    return db.scalars(select(models.AgronomicRule).where(models.AgronomicRule.id == agrorule_id)).first()

def get_agrorules_db(db: Session, skip: int, limit: int):
    return db.scalars(select(models.AgronomicRule).offset(skip).limit(limit)).all()

def update_agrorule_db(db: Session, agrorule_id: int, agrorules_update: schemas.AgronomicRuleUpdate):
    db_agrorules = db.scalars(select(models.AgronomicRule).where(models.AgronomicRule.id == agrorule_id)).first()
    if db_agrorules:
        update_data = agrorules_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_agrorules, field, value)
        db.commit()
        db.refresh(db_agrorules)
    return db_agrorules

def delete_agrorule_db(db: Session, agrorule_id: int):
    db_agrorules = db.scalars(select(models.AgronomicRule).where(models.AgronomicRule.id == agrorule_id)).first()
    if db_agrorules:
        db.delete(db_agrorules)
        db.commit()
    return db_agrorules
