from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Annotated, List

import schemas, models
from database import get_db
from fastapi.responses import Response

router = APIRouter(prefix="/detections", tags=["detections"])


@router.post("/", response_model=schemas.Detection)
async def create_detection(
        greenhouse_id: Annotated[int, Form(..., description="ID теплицы")],
        photo: UploadFile = File(..., description="Оригинальное фото"),
        db: Session = Depends(get_db)
):
    """
    Создать новую детекцию
    """
    # 1. Валидация файла
    if not photo.content_type or not photo.content_type.startswith('image/'):
        raise HTTPException(400, "Файл должен быть изображением")

    # 2. Чтение файла
    try:
        photo_bytes = await photo.read()
    except Exception as e:
        raise HTTPException(400, f"Ошибка чтения файла: {str(e)}")

    # 3. Проверка размера (макс 10MB)
    MAX_SIZE = 10 * 1024 * 1024
    if len(photo_bytes) > MAX_SIZE:
        raise HTTPException(
            400,
            f"Файл слишком большой. Максимум: {MAX_SIZE // (1024 * 1024)}MB"
        )

    # 4. Вызов ML модели для обработки
    try:
        # TODO: Заменить на вызов ML модели

        # Временные данные для примера:
        confidence_level = 0.85
        detection_photo_bytes = photo_bytes

    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки ML моделью: {str(e)}")

    # 5. Создание объекта для БД
    db_detection = models.Detection(
        photo=photo_bytes,
        detection_photo=detection_photo_bytes,
        greenhouse_id=greenhouse_id,
        confidence_level=confidence_level,

    )

    # 6. Сохранение в БД
    try:
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Ошибка сохранения в БД: {str(e)}")

    return db_detection


@router.get("/{detection_id}/photo")
async def get_photo(detection_id: int, db: Session = Depends(get_db)):
    """Получить оригинальное фото детекции"""
    detection = db.query(models.Detection).filter(
        models.Detection.id == detection_id
    ).first()

    if not detection:
        raise HTTPException(404, "Детекция не найдена")

    if not detection.photo:
        raise HTTPException(404, "Фото не найдено")

    return Response(
        content=detection.photo,
        media_type="image/jpeg"
    )


@router.get("/{detection_id}/detection-photo")
async def get_detection_photo(detection_id: int, db: Session = Depends(get_db)):
    """Получить обработанное фото с детекцией"""
    detection = db.query(models.Detection).filter(
        models.Detection.id == detection_id
    ).first()

    if not detection:
        raise HTTPException(404, "Детекция не найдена")

    if not detection.detection_photo:
        raise HTTPException(404, "Фото с детекцией не найдено")

    return Response(
        content=detection.detection_photo,
        media_type="image/jpeg"
    )

@router.get("/", response_model=List[schemas.Detection])
def get_detections(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Получить все детекции с пагинацией"""
    detections = db.query(models.Detection)\
        .order_by(models.Detection.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return detections


@router.get("/{detection_id}/photo")
async def get_photo(detection_id: int, db: Session = Depends(get_db)):
    """Получить оригинальное фото детекции"""
    detection = db.query(models.Detection).filter(
        models.Detection.id == detection_id
    ).first()

    if not detection:
        raise HTTPException(404, "Детекция не найдена")

    if not detection.photo:
        raise HTTPException(404, "Фото не найдено")

    return Response(
        content=detection.photo,
        media_type="image/jpeg"
    )


@router.get("/{detection_id}/detection-photo")
async def get_detection_photo(detection_id: int, db: Session = Depends(get_db)):
    """Получить обработанное фото с детекцией"""
    detection = db.query(models.Detection).filter(
        models.Detection.id == detection_id
    ).first()

    if not detection:
        raise HTTPException(404, "Детекция не найдена")

    if not detection.detection_photo:
        raise HTTPException(404, "Фото с детекцией не найдено")

    return Response(
        content=detection.detection_photo,
        media_type="image/jpeg"
    )


@router.delete("/{detection_id}")
def delete_detection(
        detection_id: int,
        db: Session = Depends(get_db)
):
    """Удалить детекцию по ID"""
    detection = db.query(models.Detection).filter(
        models.Detection.id == detection_id
    ).first()

    if not detection:
        raise HTTPException(404, "Детекция не найдена")

    db.delete(detection)
    db.commit()

    return {"message": "Детекция удалена", "detection_id": detection_id}


@router.put("/{detection_id}")
async def update_detection(
        detection_id: int,
        photo: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Обновить детекцию - заменить фото и обработать через ML модель"""
    detection = db.query(models.Detection).filter(
        models.Detection.id == detection_id
    ).first()

    if not detection:
        raise HTTPException(404, "Детекция не найдена")

    # Валидация файла
    if not photo.content_type.startswith('image/'):
        raise HTTPException(400, "Файл должен быть изображением")

    # Чтение файла
    photo_bytes = await photo.read()
    if len(photo_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой")

    # Обновляем оригинальное фото
    detection.photo = photo_bytes

    # Вызываем ML модель для обработки
    try:
        # TODO: Заменить на вызов вашей ML модели
        # ml_result = ml_model.process_image(photo_bytes)
        # detection.detection_photo = ml_result['processed_image']
        # detection.confidence_level = ml_result['confidence']

        # Временный код для примера
        detection.detection_photo = photo_bytes  # заменить на результат ML
        detection.confidence_level = 0.85  # заменить на результат ML
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки ML моделью: {str(e)}")

    db.commit()

    return {"message": "Детекция обновлена", "detection_id": detection_id}