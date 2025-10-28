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

        created_readings = []
        for reading_data in readings_data:
            reading = schemas.SensorReadingCreate(**reading_data)
            # Используем функцию из crud
            from crud.sensorreadings import create_sensor_reading_db
            created_reading = create_sensor_reading_db(db=db, reading=reading)
            created_readings.append(created_reading)

        return created_readings

    except Exception as e:
        raise Exception(f"Ошибка при создании показаний: {str(e)}")


def run_continuous_simulation(vg: int, vs: int):
    """Запуск непрерывной симуляции в фоновом потоке"""
    global simulation_running

    simulation_running = True
    iteration = 0

    while simulation_running:
        try:
            # Создаем новую сессию для каждого цикла
            db = SessionLocal()
            try:
                created_readings = create_single_reading(db, vg, vs)
                iteration += 1
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                      f"Авто-запись #{iteration}: создано {len(created_readings)} записей")
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                      f"Ошибка при создании записи: {e}")
            finally:
                db.close()

            # Ждем 5 минут (300 секунд)
            for _ in range(300):
                if not simulation_running:
                    break
                time.sleep(1)

        except Exception as e:
            print(f"Критическая ошибка в симуляции: {e}")
            break


# Endpoints симуляции
@router.post("/simulate-reading/")
def simulate_reading(
        vg: int = Query(0, description="Время года: 0-лето, 1-осень, 2-зима, 3-весна"),
        vs: int = Query(0, description="Время суток: 0-день, 1-ночь"),
        db: Session = Depends(get_db)
):
    """Симуляция одного измерения и сохранение в БД"""
    created_readings = create_single_reading(db, vg, vs)
    readings_data = []
    for reading in created_readings:
        reading_dict = {
            "reading_id": reading.reading_id,
            "sensor_id": reading.sensor_id,
            "value": reading.value,
            "reading_time": reading.reading_time.isoformat() if reading.reading_time else None
        }
        additional_sensor_info_dict = get_sensor_info(db, reading.sensor_id)
        greenhouse_id = additional_sensor_info_dict['greenhouse_id']
        greenhouse_info_dict = get_greenhouse_info(db, greenhouse_id)

        reading_dict["sensor_type"] = additional_sensor_info_dict["sensor_type"]
        reading_dict["greenhouse_id"] = additional_sensor_info_dict["greenhouse_id"]
        reading_dict["greenhouse_name"] = greenhouse_info_dict["greenhouse_name"]
        reading_dict["greenhouse_location"] = greenhouse_info_dict["location"]
        reading_dict["greenhouse_description"] = greenhouse_info_dict["description"]
        readings_data.append(reading_dict)

    return readings_data


@router.post("/start-auto-simulation/")
def start_auto_simulation(
        vg: int = Query(0, description="Время года: 0-лето, 1-осень, 2-зима, 3-весна"),
        vs: int = Query(0, description="Время суток: 0-день, 1-ночь")
):
    """Запуск автоматической симуляции каждые 5 минут"""
    global simulation_task, simulation_running

    if simulation_running:
        raise HTTPException(
            status_code=400,
            detail="Автоматическая симуляция уже запущена"
        )

    # Запускаем в отдельном потоке
    simulation_task = threading.Thread(
        target=run_continuous_simulation,
        args=(vg, vs),
        daemon=True
    )
    simulation_task.start()

    return {
        "message": "Автоматическая симуляция запущена",
        "interval_minutes": 5,
        "season": vg,
        "time_of_day": vs,
        "status": "running"
    }


@router.post("/stop-auto-simulation/")
def stop_auto_simulation():
    """Остановка автоматической симуляции"""
    global simulation_running

    if not simulation_running:
        raise HTTPException(
            status_code=400,
            detail="Автоматическая симуляция не запущена"
        )

    simulation_running = False

    return {
        "message": "Автоматическая симуляция остановлена",
        "status": "stopped"
    }


@router.get("/simulation-status/")
def get_simulation_status():
    """Получение статуса автоматической симуляции"""
    global simulation_running

    return {
        "simulation_running": simulation_running,
        "status": "running" if simulation_running else "stopped"
    }
