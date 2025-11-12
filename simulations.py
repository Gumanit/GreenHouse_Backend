from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, APIRouter
from sqlalchemy.orm import Session
import models, schemas
from crud.sensors import get_sensor_info, get_greenhouse_info
from database import SessionLocal,  get_db
import random
from decimal import Decimal
from datetime import datetime
import threading
import time
from crud.reports import create_report_row
import time
import threading
from datetime import datetime

# Глобальная переменная для управления автоматической симуляцией
simulation_task = None
simulation_running = False

router = APIRouter(
    prefix="/simulations",
    tags=["simulations"],
)

def generate_sensor_data(season, time_of_day):
    """Генерация данных датчиков"""

    def generate_co2():
        return Decimal(str(random.randint(400, 1500)))

    def generate_temperature(season, time_of_day):
        season_temps = {
            0: {'day': (20, 35), 'night': (15, 25)},
            1: {'day': (10, 20), 'night': (5, 15)},
            2: {'day': (5, 15), 'night': (0, 10)},
            3: {'day': (15, 25), 'night': (10, 18)}
        }
        time_key = 'day' if time_of_day == 0 else 'night'
        temp_range = season_temps[season][time_key]
        return Decimal(str(round(random.uniform(temp_range[0], temp_range[1]), 2)))

    def generate_humidity(season, time_of_day):
        season_humidity = {
            0: {'day': (40, 70), 'night': (50, 80)},
            1: {'day': (50, 80), 'night': (60, 90)},
            2: {'day': (30, 60), 'night': (40, 70)},
            3: {'day': (40, 75), 'night': (50, 85)}
        }
        time_key = 'day' if time_of_day == 0 else 'night'
        humidity_range = season_humidity[season][time_key]
        return Decimal(str(round(random.uniform(humidity_range[0], humidity_range[1]), 2)))

    return {
        'temperature': generate_temperature(season, time_of_day),
        'humidity': generate_humidity(season, time_of_day),
        'co2': generate_co2()
    }


def create_single_reading(db: Session, vg: int, vs: int):
    """Создание одного набора показаний для всех датчиков"""
    try:
        # Получаем датчики из базы
        from crud.sensors import get_sensors_db
        sensors = get_sensors_db(db)

        if not sensors:
            raise Exception("В базе нет датчиков. Сначала создайте датчики через API /sensors/")

        # Фильтруем датчики по типам
        temp_sensors = [s for s in sensors if s.type == 'temperature']
        humidity_sensors = [s for s in sensors if s.type == 'humidity']
        co2_sensors = [s for s in sensors if s.type == 'co2']

        sensor_data = generate_sensor_data(vg, vs)
        readings_data = []
        for temp_sensor in temp_sensors:
            if temp_sensor:
                readings_data.append({"sensor_id": temp_sensor.sensor_id, "value": sensor_data['temperature']})
        for humidity_sensor in humidity_sensors:
            if humidity_sensor:
                readings_data.append({"sensor_id": humidity_sensor.sensor_id, "value": sensor_data['humidity']})
        for co2_sensor in co2_sensors:
            if co2_sensor:
                readings_data.append({"sensor_id": co2_sensor.sensor_id, "value": sensor_data['co2']})

        if not readings_data:
            raise Exception("Не найдены датчики подходящих типов (temperature, humidity, co2)")

        return collect_readings_data(readings_data, db)

    except Exception as e:
        raise Exception(f"Ошибка при создании показаний: {str(e)}")


def collect_readings_data(created_readings, db: Session = Depends(get_db)):
    readings_data = []
    for reading in created_readings:
        reading_dict = {
            "sensor_id": reading["sensor_id"],
            "value": reading["value"],
            "reading_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        additional_sensor_info_dict = get_sensor_info(db, reading["sensor_id"])
        greenhouse_id = additional_sensor_info_dict['greenhouse_id']
        greenhouse_info_dict = get_greenhouse_info(db, greenhouse_id)

        reading_dict["type"] = additional_sensor_info_dict["type"]
        reading_dict["greenhouse_id"] = additional_sensor_info_dict["greenhouse_id"]
        reading_dict["greenhouse_name"] = greenhouse_info_dict["greenhouse_name"]
        reading_dict["greenhouse_location"] = greenhouse_info_dict["location"]
        reading_dict["greenhouse_description"] = greenhouse_info_dict["description"]
        readings_data.append(reading_dict)
    return readings_data

def group_by_greenhouse_id(readings_data):
    greenhouse_sensors = {}

    for sensor in readings_data:
        greenhouse_id = sensor['greenhouse_id']

        if greenhouse_id not in greenhouse_sensors:
            greenhouse_sensors[greenhouse_id] = []

        greenhouse_sensors[greenhouse_id].append(sensor)

    return greenhouse_sensors

def get_predict(curr_sensor, other_sensors):
    return -1


def create_single_report_row(db: Session, greenhouse_id: int, sensors: list):
    """
    Создание одной строки отчета для теплицы
    """
    try:
        print(f"Создание отчета для теплицы {greenhouse_id} с {len(sensors)} датчиками")

        # Инициализация строки отчета
        row = {
            "greenhouse_id": greenhouse_id,
            "report_time": datetime.now()
        }

        # Собираем данные по типам датчиков
        sensor_data = {}
        for sensor in sensors:
            sensor_type = sensor["type"]
            sensor_data[sensor_type] = {
                "value": Decimal(str(float(sensor["value"]))),
                "pred": Decimal("-1.0"),  # заглушка для прогноза
                "command": Decimal("1.0")  # команда как Decimal
            }

        # Заполняем поля отчета
        if "temperature" in sensor_data:
            row["temperature_value"] = sensor_data["temperature"]["value"]
            row["temperature_pred"] = sensor_data["temperature"]["pred"]
            row["command_temperature"] = sensor_data["temperature"]["command"]

        if "humidity" in sensor_data:
            row["humidity_value"] = sensor_data["humidity"]["value"]
            row["humidity_pred"] = sensor_data["humidity"]["pred"]
            row["command_humidity"] = sensor_data["humidity"]["command"]

        if "co2" in sensor_data:
            row["co2_value"] = sensor_data["co2"]["value"]
            row["co2_pred"] = sensor_data["co2"]["pred"]
            row["command_co2"] = sensor_data["co2"]["command"]


        # Сохранение в БД
        from crud.reports import create_report_db
        report_create = schemas.ReportCreate(**row)
        result = create_report_db(db, report_create)
        return result

    except Exception as e:
        print(f"  ❌ Критическая ошибка: {e}")
        raise Exception(f"Ошибка при создании отчета для теплицы {greenhouse_id}: {str(e)}")

# Глобальная переменная для управления периодическим созданием отчетов
reporting_active = False
reporting_thread = None


def create_report_rows(db):
    """
    Создание отчетов для всех теплиц

    Args:
        db: подключение к БД (Session)

    Returns:
        dict: результат выполнения операции
    """
    try:

        created_readings = create_single_reading(db, 0, 0)

        # 1. Сбор данных
        #readings_data = collect_readings_data(db)
        readings_data = created_readings

        if not readings_data:
            return {"status": "error", "message": "Нет данных для создания отчетов"}

        # 2. Группировка по теплицам
        greenhouses = group_by_greenhouse_id(readings_data)

        # 3. Создание отчетов для каждой теплицы
        reports_created = 0
        for greenhouse_id, sensors in greenhouses.items():
            try:
                create_single_report_row(db, greenhouse_id, sensors)
                reports_created += 1
            except Exception as e:
                print(f"Ошибка при создании отчета для теплицы {greenhouse_id}: {e}")

        result = {
            "status": "success",
            "message": f"Создано отчетов: {reports_created} для {len(greenhouses)} теплиц",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reports_created": reports_created,
            "greenhouses_processed": len(greenhouses)
        }

        return result

    except Exception as e:
        error_msg = f"Ошибка при создании отчетов: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


def start_periodic_reporting(db: Session, interval_minutes: int = 3):
    """
    Запуск периодического создания отчетов

    Args:
        db: подключение к БД
        interval_minutes: интервал в минутах
    """
    global reporting_active

    def reporting_loop():
        while reporting_active:
            try:
                create_report_rows(db)
            except Exception as e:
                print(f"Ошибка в периодическом создании отчетов: {e}")

            # Ожидание указанного интервала
            time.sleep(interval_minutes * 60)

    reporting_active = True
    global reporting_thread
    reporting_thread = threading.Thread(target=reporting_loop, daemon=True)
    reporting_thread.start()

    return {"status": "started", "interval_minutes": interval_minutes}


def stop_periodic_reporting():
    """
    Остановка периодического создания отчетов
    """
    global reporting_active
    reporting_active = False

    if reporting_thread and reporting_thread.is_alive():
        reporting_thread.join(timeout=5)

    return {"status": "stopped", "message": "Периодическое создание отчетов остановлено"}


# Эндпоинты для управления периодическими отчетами
@router.post("/start-periodic-reports/")
def start_periodic_reports_endpoint(
        background_tasks: BackgroundTasks,
        interval_minutes: int = Query(3, description="Интервал создания отчетов в минутах"),
        db: Session = Depends(get_db)
):
    """Запуск автоматического создания отчетов"""
    global reporting_active

    if reporting_active:
        raise HTTPException(status_code=400, detail="Периодическое создание отчетов уже запущено")

    result = start_periodic_reporting(db, interval_minutes)
    return result


@router.post("/stop-periodic-reports/")
def stop_periodic_reports_endpoint():
    """Остановка автоматического создания отчетов"""
    global reporting_active

    if not reporting_active:
        raise HTTPException(status_code=400, detail="Периодическое создание отчетов не запущено")

    result = stop_periodic_reporting()
    return result


@router.post("/create-reports-now/")
def create_reports_now_endpoint(db: Session = Depends(get_db)):
    """Немедленное создание отчетов"""
    result = create_report_rows(db)
    return result


@router.get("/reporting-status/")
def get_reporting_status():
    """Получение статуса периодического создания отчетов"""
    return {
        "reporting_active": reporting_active,
        "interval_minutes": 3
    }

# Endpoint симуляции
@router.get("/simulate-reading/")
def simulate_reading(
        vg: int = Query(0, description="Время года: 0-лето, 1-осень, 2-зима, 3-весна"),
        vs: int = Query(0, description="Время суток: 0-день, 1-ночь"),
        db: Session = Depends(get_db)
):
    """Симуляция одного измерения"""
    return create_single_reading(db, vg, vs)