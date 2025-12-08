from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Annotated, List
import pickle
import cv2
import numpy as np
from PIL import Image, ImageDraw
from io import BytesIO
from skimage.measure import label, regionprops
from skimage.feature import hog
import schemas, models
from database import get_db
from fastapi.responses import Response

router = APIRouter(prefix="/detections", tags=["detections"])

# Загружаем ML модель
try:
    with open('svm_pipeline.pkl', 'rb') as file:
        ml_model = pickle.load(file)
    print("ML модель успешно загружена")
except Exception as e:
    print(f"Ошибка загрузки ML модели: {e}")
    ml_model = None

# Константы для HOG
N = 128  # Количество пикселей в строке
M = 128  # Количество пикселей в столбце
K = 8  # Размерность ячейки
P = 2  # Размерность блока


def find_green_candidates(image, green_threshold=40):
    """Находит зеленые регионы как кандидаты на сорняки"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 40, 40])
    upper_green = np.array([90, 255, 255])

    green_mask_1 = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((4, 4), np.uint8)
    green_mask = cv2.morphologyEx(green_mask_1, cv2.MORPH_CLOSE, kernel, iterations=4)

    contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    clean_mask = np.zeros_like(green_mask)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 100:
            cv2.drawContours(clean_mask, [contour], -1, 255, -1)

    clean_mask = cv2.GaussianBlur(clean_mask, (3, 3), 0)
    _, clean_mask = cv2.threshold(clean_mask, 127, 255, cv2.THRESH_BINARY)

    return clean_mask


def mask_to_coordinates(mask, original_image, min_area=100):
    """Конвертирует маску в координаты bbox"""
    labeled_mask = label(mask)
    detections = []
    gray_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)

    for region in regionprops(labeled_mask):
        if region.area >= min_area:
            min_row, min_col, max_row, max_col = region.bbox
            bbox_coords = (min_col, min_row, max_col, max_row)

            crop_mask = mask[min_row:max_row, min_col:max_col]
            gray_pixels = gray_image[min_row:max_row, min_col:max_col]
            gray_pixels[crop_mask == 0] = 0

            detections.append((*bbox_coords, gray_pixels))

    return detections


def process_image_with_ml(image_bytes):
    """Обрабатывает изображение через ML модель"""
    # Конвертируем bytes в numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Не удалось декодировать изображение")

    # 1. Находим зеленые кандидаты
    green_mask = find_green_candidates(img)

    # 2. Получаем bounding boxes
    bboxes = mask_to_coordinates(green_mask, img)

    # 3. Обрабатываем каждый bbox через модель
    detected_bboxes = []  # переименовали переменную
    confidence_levels = []

    for bbox in bboxes:
        bbox_gray = np.array(bbox[4])
        h, w = bbox_gray.shape[:2]

        # Пропускаем слишком маленькие bbox
        if h < 10 or w < 10:
            continue

        bbox_gray_resized = cv2.resize(bbox_gray, (N, M))

        # Извлекаем HOG фичи
        hog_features = hog(
            bbox_gray_resized,
            orientations=8,
            pixels_per_cell=(K, K),
            cells_per_block=(P, P),
            feature_vector=True
        )

        # Предсказание модели
        predict = ml_model.predict_proba([hog_features])

        # Если вероятность сорняка > 0.42
        if predict[0][1] > 0.42:
            detected_bboxes.append(bbox[:4])  # только координаты
            confidence_levels.append(predict[0][1])

    # 4. Рисуем bounding boxes на изображении
    pil_image = Image.open(BytesIO(image_bytes))
    draw = ImageDraw.Draw(pil_image)

    for detection in detected_bboxes:
        x1, y1, x2, y2 = detection
        draw.rectangle([x1, y1, x2, y2], outline="red", width=3)

    # Конвертируем обработанное изображение в bytes
    img_byte_arr = BytesIO()
    pil_image.save(img_byte_arr, format='JPEG')
    processed_image_bytes = img_byte_arr.getvalue()

    # Рассчитываем средний confidence_level
    avg_confidence = np.mean(confidence_levels) if confidence_levels else 0.0

    detection_count = len(detected_bboxes)  # сохраняем количество детекций

    print(f"Обработано изображение: {detection_count} детекций, confidence: {avg_confidence}")

    return {
        'processed_image': processed_image_bytes,
        'confidence_level': float(avg_confidence),
        'detection_count': detection_count
    }


@router.post("/", response_model=schemas.Detection)
async def create_detection(
        greenhouse_id: Annotated[int, Form(..., description="ID теплицы")],
        photo: UploadFile = File(..., description="Оригинальное фото"),
        db: Session = Depends(get_db)
):
    """
    Создать новую детекцию
    """
    # Проверка ML модели
    if ml_model is None:
        raise HTTPException(500, "ML модель не загружена")

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
        ml_result = process_image_with_ml(photo_bytes)
        confidence_level = ml_result['confidence_level']
        detection_photo_bytes = ml_result['processed_image']
        detection_count = ml_result['detection_count']

        print(f"Обработано изображение: {detection_count} детекций, confidence: {confidence_level}")

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


@router.get("/", response_model=List[schemas.Detection])
def get_detections(
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000)
):
    """Получить все детекции с пагинацией"""
    detections = db.query(models.Detection) \
        .order_by(models.Detection.created_at.desc()) \
        .offset(skip) \
        .limit(limit) \
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
    # Проверка ML модели
    if ml_model is None:
        raise HTTPException(500, "ML модель не загружена")

    detection = db.query(models.Detection).filter(
        models.Detection.id == detection_id
    ).first()

    if not detection:
        raise HTTPException(404, "Детекция не найдена")

    # Валидация файла
    if not photo.content_type or not photo.content_type.startswith('image/'):
        raise HTTPException(400, "Файл должен быть изображением")

    # Чтение файла
    try:
        photo_bytes = await photo.read()
    except Exception as e:
        raise HTTPException(400, f"Ошибка чтения файла: {str(e)}")

    if len(photo_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой (макс. 10MB)")

    # Обновляем оригинальное фото
    detection.photo = photo_bytes

    # Вызываем ML модель для обработки
    try:
        ml_result = process_image_with_ml(photo_bytes)
        detection.detection_photo = ml_result['processed_image']
        detection.confidence_level = ml_result['confidence_level']

        print(f"Обновлено изображение: confidence: {detection.confidence_level}")

    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки ML моделью: {str(e)}")

    db.commit()
    db.refresh(detection)

    return {
        "message": "Детекция обновлена",
        "detection_id": detection_id,
        "confidence_level": detection.confidence_level
    }