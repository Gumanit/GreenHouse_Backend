from datetime import datetime
from sqlalchemy import desc
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, Query
from database import get_db

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)

@router.get("/", response_model=List[schemas.ReportRead])
def read_reports(
    skip: int = 0,
    limit: int = 100,
    greenhouse_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    reports = get_reports_db(db, skip=skip, limit=limit, greenhouse_id=greenhouse_id)
    return reports

@router.get("/{report_id}", response_model=schemas.ReportRead)
def read_report(report_id: int, db: Session = Depends(get_db)):
    db_report = get_report_db(db, report_id=report_id)
    if db_report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return db_report


@router.get("/greenhouse/{greenhouse_id}/latest", response_model=schemas.ReportRead)
def read_latest_report(greenhouse_id: int, db: Session = Depends(get_db)):
    db_report = get_latest_report_db(db, greenhouse_id=greenhouse_id)
    if db_report is None:
        raise HTTPException(status_code=404, detail="No reports found for this greenhouse")
    return db_report


@router.get("/greenhouse/{greenhouse_id}", response_model=List[schemas.ReportRead])
def read_reports_by_greenhouse(
    greenhouse_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    reports = get_reports_by_greenhouse_db(db, greenhouse_id=greenhouse_id, skip=skip, limit=limit)
    return reports



@router.post("/", response_model=schemas.ReportRead)
def create_report(report: schemas.ReportCreate, db: Session = Depends(get_db)):
    return create_report_db(db=db, report=report)


@router.put("/{report_id}", response_model=schemas.ReportRead)
def update_report(
    report_id: int,
    report_update: schemas.ReportUpdate,
    db: Session = Depends(get_db)
):
    db_report = update_report_db(db, report_id=report_id, report_update=report_update)
    if db_report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return db_report

@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    db_report = delete_report_id_db(db, report_id=report_id)
    if db_report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted successfully"}

@router.delete("/")
def delete_report(db: Session = Depends(get_db)):
    try:
        deleted_count = delete_all_reports_db(db)
        return {"message": f"Удалено {deleted_count} отчетов"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при очистке таблицы: {str(e)}"
        )

# Основные CRUD функции
def get_report_db(db: Session, report_id: int):
    return db.query(models.Report).filter(models.Report.id == report_id).first()


def get_reports_db(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        greenhouse_id: Optional[int] = None
):
    query = db.query(models.Report)

    if greenhouse_id is not None:
        query = query.filter(models.Report.greenhouse_id == greenhouse_id)

    return query.order_by(desc(models.Report.report_time)).offset(skip).limit(limit).all()


def create_report_db(db: Session, report: schemas.ReportCreate):
    # Проверяем существование теплицы
    greenhouse = db.query(models.Greenhouse).filter(
        models.Greenhouse.greenhouse_id == report.greenhouse_id
    ).first()

    if not greenhouse:
        raise HTTPException(status_code=400, detail="Greenhouse not found")

    db_report = models.Report(**report.model_dump())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def update_report_db(db: Session, report_id: int, report_update: schemas.ReportUpdate):
    db_report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if db_report:
        update_data = report_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_report, field, value)
        db.commit()
        db.refresh(db_report)
    return db_report


def delete_report_id_db(db: Session, report_id: int):
    db_report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if db_report:
        db.delete(db_report)
        db.commit()
    return db_report

def delete_all_reports_db(db: Session):
    """Очистка всей таблицы отчетов"""
    try:
        # Удаляем все записи из таблицы
        deleted_count = db.query(models.Report).delete()
        db.commit()
        return deleted_count  # Возвращаем количество удаленных записей
    except Exception as e:
        db.rollback()
        raise e


# Специальные функции для отчетов
def get_reports_by_greenhouse_db(
        db: Session,
        greenhouse_id: int,
        skip: int = 0,
        limit: int = 100
):
    return (
        db.query(models.Report)
        .filter(models.Report.greenhouse_id == greenhouse_id)
        .order_by(desc(models.Report.report_time))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_latest_report_db(db: Session, greenhouse_id: int):
    return (
        db.query(models.Report)
        .filter(models.Report.greenhouse_id == greenhouse_id)
        .order_by(desc(models.Report.report_time))
        .first()
    )


def get_reports_by_time_range_db(
        db: Session,
        greenhouse_id: int,
        start_time: datetime,
        end_time: datetime,
        skip: int = 0,
        limit: int = 100
):
    return (
        db.query(models.Report)
        .filter(
            models.Report.greenhouse_id == greenhouse_id,
            models.Report.report_time >= start_time,
            models.Report.report_time <= end_time
        )
        .order_by(desc(models.Report.report_time))
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_report_row(db: Session, row_data: dict):
    """
    Создание записи отчета в БД

    Args:
        db: подключение к БД
        row_data: словарь с данными отчета

    Returns:
        созданная запись Report
    """
    # Добавляем дату создания отчета, если не указана
    if "report_date" not in row_data:
        row_data["report_date"] = datetime.now()

    # Создаем объект модели Report из данных
    db_report = models.Report(**row_data)

    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report