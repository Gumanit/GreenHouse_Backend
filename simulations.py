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
        # Инициализация строки отчета
        row = {
            "greenhouse_id": greenhouse_id,
            "report_date": datetime.now()
        }

        # Обработка каждого датчика
        for i in range(len(sensors)):
            curr_sensor = sensors[i]

            # Запись текущего значения
            row[curr_sensor["type"]] = float(
                curr_sensor["value"])  # В поле с названием типа сенсора заносим его значение

            # Формирование массива других датчиков
            if i > 0 and i < len(sensors) - 1:
                other_sensors = sensors[:i] + sensors[i + 1:]
            elif i == 0:
                other_sensors = sensors[1:]
            else:  # i == len(sensors) - 1
                other_sensors = sensors[:i]

            # Прогнозирование
            prediction = get_predict(curr_sensor, other_sensors)
            row[curr_sensor["type"] + "_pred"] = float(prediction)

            # Формирование команды
            row["command_" + curr_sensor["type"]] = "1"  # пока константа

        # Сохранение в БД
        return create_report_row(db, row)

    except Exception as e:
        db.rollback()
        raise Exception(f"Ошибка при создании отчета для теплицы {greenhouse_id}: {str(e)}")

# Endpoint симуляции
@router.get("/simulate-reading/")
def simulate_reading(
        vg: int = Query(0, description="Время года: 0-лето, 1-осень, 2-зима, 3-весна"),
        vs: int = Query(0, description="Время суток: 0-день, 1-ночь"),
        db: Session = Depends(get_db)
):
    """Симуляция одного измерения"""
    return create_single_reading(db, vg, vs)