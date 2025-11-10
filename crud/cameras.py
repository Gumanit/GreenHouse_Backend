from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, Query
from database import get_db

router = APIRouter(
    prefix="/cameras",
    tags=["cameras"],
)

@router.post("/create")
def create_camera(content: schemas.CameraCreate, db: Session = Depends(get_db())):
    return create_camera_db(content, db)

@router.get("/read/{id}")
def read_camera(id :int, db: Session = Depends(get_db())):
    camera = read_camera_db(id, db)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera doesn't exist")
    return camera

@router.get("/read")
def read_cameras(skip: int, limit: int, db: Session = Depends(get_db())):
    return read_cameras_db(skip, limit, db)

@router.put("/update/{id}")
def update_camera(content: schemas.CameraUpdate, id: int, db: Session = Depends(get_db())):
    camera = update_camera_db(content, id, db)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera doesn't exist")
    return camera

@router.delete("/delete/{id}")
def delete_camera(id: int, db: Session = Depends(get_db())):
    camera = delete_camera_db(id, db)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera doesn't exist")
    return {"message": "Camera deleted successfully"}

def create_camera_db(content: schemas.CameraCreate, db: Session):
    created_camera = models.Camera(**content.model_dump())
    db.add(created_camera)
    db.commit()
    db.refresh(created_camera)
    return created_camera

def read_camera_db(id: int, db: Session):
    camera = db.scalars(select(models.Camera).where(models.Camera.id == id)).first()
    return camera

def read_cameras_db(skip: int, limit: int, db: Session):
    return db.scalars(select(models.Camera).offset(skip).limit(limit)).all()

def update_camera_db(content: schemas.CameraUpdate, id: int, db: Session):
    updated_camera = db.scalars(select(models.Camera).where(models.Camera.id == id)).first()
    if updated_camera:
        updated_data = schemas.Camera(**content.model_dump(exclude_unset=True))
        for field, value in updated_data.items():
            setattr(updated_camera, field, value)
        db.commit()
        db.refresh(updated_camera)
    return updated_camera

def delete_camera_db(id: int, db: Session):
    deleted_camera = db.scalars(select(models.Camera).where(models.Camera.id == id)).first()
    if deleted_camera:
        db.delete(deleted_camera)
        db.commit()
    return deleted_camera