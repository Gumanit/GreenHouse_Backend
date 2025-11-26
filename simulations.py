import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
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
import tensorflow as tf
from tensorflow import keras

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


def predict_ml(sensor_data: dict, report_time: datetime, model_path: str) -> Decimal:
    """
    ML предсказания на основе весов моделей
    """
    try:
        # Загружаем веса модели
        with open(model_path, 'rb') as f:
            model_weights = pickle.load(f)

        # Расчет освещенности
        hour = report_time.hour
        if 6 <= hour < 23:
            illuminance = np.random.uniform(800, 2000)
        else:
            illuminance = np.random.uniform(0, 50)

        # Подготовка признаков
        features = {
            'greenhous_temperature_celsius': float(sensor_data['temperature']),
            'greenhouse_humidity_percentage': float(sensor_data['humidity']),
            'greenhouse_illuminance_lux': illuminance,
            'online_temperature_celsius': float(sensor_data['temperature']) - 2.0,
            'online_humidity_percentage': float(sensor_data['humidity']) - 5.0,
            'greenhouse_total_volatile_organic_compounds_ppb': 200.0,
            'greenhouse_equivalent_co2_ppm': float(sensor_data['co2']),
            'hour_sin': np.sin(2 * np.pi * report_time.hour / 24),
            'hour_cos': np.cos(2 * np.pi * report_time.hour / 24),
            'minute_sin': np.sin(2 * np.pi * report_time.minute / 60),
            'minute_cos': np.cos(2 * np.pi * report_time.minute / 60),
            'day_of_week_sin': np.sin(2 * np.pi * report_time.weekday() / 7),
            'day_of_week_cos': np.cos(2 * np.pi * report_time.weekday() / 7),
            'day_of_month_sin': np.sin(2 * np.pi * (report_time.day - 1) / 31),
            'day_of_month_cos': np.cos(2 * np.pi * (report_time.day - 1) / 31),
            'month_sin': np.sin(2 * np.pi * (report_time.month - 1) / 12),
            'month_cos': np.cos(2 * np.pi * (report_time.month - 1) / 12),
            'day_of_year_sin': np.sin(2 * np.pi * (report_time.timetuple().tm_yday - 1) / 365),
            'day_of_year_cos': np.cos(2 * np.pi * (report_time.timetuple().tm_yday - 1) / 365)
        }

        # Создаем входные данные
        input_df = pd.DataFrame([features])[model_weights['feature_names']]

        # Масштабируем
        input_scaled = model_weights['scaler'].transform(input_df)

        # Прямой проход (предсказание) без использования класса LinearModel
        # y_pred = X @ w + b
        prediction = input_scaled @ model_weights['w'] + model_weights['b']

        return Decimal(str(round(prediction[0], 2)))

    except Exception as e:
        print(f"⚠️ Ошибка ML предсказания влажности: {e}")
        return Decimal("-1.0")


def predict_co2_nn(sensor_data: dict, report_time: datetime,
                           weights_path: str = 'greenhouse_co2_nn_weights.weights.h5',
                           scalers_path: str = 'greenhouse_co2_nn_scalers.pkl') -> Decimal:
    """
    Предсказание CO2 с использованием весов нейронной сети
    """

    def create_co2_nn_model(input_dim=19):
        """
        Создание архитектуры нейронной сети (должна совпадать с обученной моделью)
        """
        model = keras.Sequential([
            # Первый скрытый слой
            keras.layers.Dense(128, activation='relu', input_shape=(input_dim,),
                               kernel_regularizer=keras.regularizers.l2(0.001)),
            keras.layers.BatchNormalization(),
            keras.layers.Dropout(0.3),

            # Второй скрытый слой
            keras.layers.Dense(64, activation='relu',
                               kernel_regularizer=keras.regularizers.l2(0.001)),
            keras.layers.BatchNormalization(),
            keras.layers.Dropout(0.3),

            # Третий скрытый слой
            keras.layers.Dense(32, activation='relu',
                               kernel_regularizer=keras.regularizers.l2(0.001)),
            keras.layers.Dropout(0.2),

            # Выходной слой
            keras.layers.Dense(1, activation='linear')
        ])

        return model

    try:
        # Загружаем scalers и метаданные
        with open(scalers_path, 'rb') as f:
            scalers_data = pickle.load(f)

        scaler_X = scalers_data['scaler_X']
        scaler_y = scalers_data['scaler_y']
        feature_names = scalers_data['feature_names']
        input_dim = scalers_data['input_dim']

        print(f"  🔧 Загружены scalers. Размерность: {input_dim}, Признаков: {len(feature_names)}")

        # Создаем модель с такой же архитектурой
        model = create_co2_nn_model(input_dim=input_dim)

        # Загружаем веса
        model.load_weights(weights_path)
        print("  🔧 Веса модели загружены")

        # Компилируем модель
        model.compile(
            optimizer='adam',
            loss='mse',
            metrics=['mae']
        )

        # Расчет освещенности по времени суток
        hour = report_time.hour
        if 6 <= hour < 23:
            illuminance = np.random.uniform(800, 2000)
        else:
            illuminance = np.random.uniform(0, 50)

        # Подготовка признаков в ТОЧНОМ порядке как при обучении
        features = {
            'greenhous_temperature_celsius': float(sensor_data['temperature']),
            'greenhouse_humidity_percentage': float(sensor_data['humidity']),
            'greenhouse_illuminance_lux': illuminance,
            'online_temperature_celsius': float(sensor_data['temperature']) - 2.0,
            'online_humidity_percentage': float(sensor_data['humidity']) - 5.0,
            'greenhouse_total_volatile_organic_compounds_ppb': 200.0,
            'greenhouse_equivalent_co2_ppm': float(sensor_data['co2']),
            'hour_sin': np.sin(2 * np.pi * report_time.hour / 24),
            'hour_cos': np.cos(2 * np.pi * report_time.hour / 24),
            'minute_sin': np.sin(2 * np.pi * report_time.minute / 60),
            'minute_cos': np.cos(2 * np.pi * report_time.minute / 60),
            'day_of_week_sin': np.sin(2 * np.pi * report_time.weekday() / 7),
            'day_of_week_cos': np.cos(2 * np.pi * report_time.weekday() / 7),
            'day_of_month_sin': np.sin(2 * np.pi * (report_time.day - 1) / 31),
            'day_of_month_cos': np.cos(2 * np.pi * (report_time.day - 1) / 31),
            'month_sin': np.sin(2 * np.pi * (report_time.month - 1) / 12),
            'month_cos': np.cos(2 * np.pi * (report_time.month - 1) / 12),
            'day_of_year_sin': np.sin(2 * np.pi * (report_time.timetuple().tm_yday - 1) / 365),
            'day_of_year_cos': np.cos(2 * np.pi * (report_time.timetuple().tm_yday - 1) / 365)
        }

        # Создаем входные данные в ПРАВИЛЬНОМ порядке
        input_data = np.array([[features[feature] for feature in feature_names]])
        print(f"  🔧 Подготовлены данные. Форма: {input_data.shape}")

        # Масштабируем входные данные
        input_scaled = scaler_X.transform(input_data)

        # Предсказание
        prediction_scaled = model.predict(input_scaled, verbose=0)

        # Обратное масштабирование предсказания
        prediction = scaler_y.inverse_transform(prediction_scaled)

        result = Decimal(str(round(prediction[0][0], 2)))
        print(f"  🔧 Предсказание CO2: {result} ppm")

        return result

    except Exception as e:
        print(f"⚠️ Ошибка предсказания CO2 (веса): {e}")
        return Decimal("-1.0")


def create_single_report_row(db: Session, greenhouse_id: int, sensors: list):
    """
    Создание одной строки отчета для теплицы с ML предсказаниями
    """
    try:
        print(f"Создание отчета для теплицы {greenhouse_id} с {len(sensors)} датчиками")

        # Инициализация строки отчета
        current_time = datetime.now()
        row = {
            "greenhouse_id": greenhouse_id,
            "report_time": current_time
        }

        # Собираем данные по типам датчиков
        sensor_data = {}

        # Сначала собираем все сырые данные
        raw_sensor_data = {}
        for sensor in sensors:
            sensor_type = sensor["type"]
            raw_sensor_data[sensor_type] = float(sensor["value"])

        # 🔮 ML ПРЕДСКАЗАНИЕ ДЛЯ ВЛАЖНОСТИ
        if all(key in raw_sensor_data for key in ['temperature', 'humidity', 'co2']):
            try:
                ml_prediction_humidity = predict_ml(raw_sensor_data, current_time, 'greenhouse_humidity_model_weights.pkl')
            except Exception as e:
                print(f"  ⚠️ Ошибка ML предсказания влажности: {e}")
                ml_prediction_humidity = Decimal("-1.0")
        else:
            ml_prediction_humidity = Decimal("-1.0")

        # 🔮 ML ПРЕДСКАЗАНИЕ ДЛЯ CO2 (НЕЙРОННАЯ СЕТЬ С ВЕСАМИ)
        if all(key in raw_sensor_data for key in ['temperature', 'humidity', 'co2']):
            try:
                ml_prediction_co2 = predict_co2_nn(raw_sensor_data, current_time)
            except Exception as e:
                print(f"  ⚠️ Ошибка ML предсказания CO2: {e}")
                ml_prediction_co2 = Decimal("-1.0")
        else:
            ml_prediction_co2 = Decimal("-1.0")

        # 🔮 ML ПРЕДСКАЗАНИЕ ДЛЯ ВЛАЖНОСТИ
        if all(key in raw_sensor_data for key in ['temperature', 'humidity', 'co2']):
            try:
                ml_prediction_humidity = predict_ml(raw_sensor_data, current_time,
                                                    'greenhouse_humidity_model_weights.pkl')
                print(f"  ✅ ML предсказание влажности: {ml_prediction_humidity}%")
            except Exception as e:
                print(f"  ⚠️ Ошибка ML предсказания влажности: {e}")
                ml_prediction_humidity = Decimal("-1.0")
        else:
            ml_prediction_humidity = Decimal("-1.0")

        # 🔮 ML ПРЕДСКАЗАНИЕ ДЛЯ CO2 (НЕЙРОННАЯ СЕТЬ С ВЕСАМИ)
        if all(key in raw_sensor_data for key in ['temperature', 'humidity', 'co2']):
            try:
                ml_prediction_co2 = predict_co2_nn(raw_sensor_data, current_time)
                print(f"  ✅ ML предсказание CO2: {ml_prediction_co2} ppm")
            except Exception as e:
                print(f"  ⚠️ Ошибка ML предсказания CO2: {e}")
                ml_prediction_co2 = Decimal("-1.0")
        else:
            ml_prediction_co2 = Decimal("-1.0")

        # 🔮 ML ПРЕДСКАЗАНИЕ ДЛЯ ТЕМПЕРАТУРЫ
        if all(key in raw_sensor_data for key in ['temperature', 'humidity', 'co2']):
            try:
                ml_prediction_temperature = predict_ml(raw_sensor_data, current_time,
                                                       'greenhouse_temperature_model_weights.pkl')
                print(f"  ✅ ML предсказание температуры: {ml_prediction_temperature}°C")
            except Exception as e:
                print(f"  ⚠️ Ошибка ML предсказания температуры: {e}")
                ml_prediction_temperature = Decimal("-1.0")
        else:
            ml_prediction_temperature = Decimal("-1.0")

        # Формируем финальные данные сенсоров
        for sensor in sensors:
            sensor_type = sensor["type"]
            curr_val_sensor = Decimal(str(raw_sensor_data[sensor_type]))

            if sensor_type == "humidity":
                if ml_prediction_humidity != Decimal("-1.0"):
                    curr_val_float = float(curr_val_sensor)
                    pred_val_float = float(ml_prediction_humidity)

                    # Процент отклонения: (предсказание - текущее) / текущее * 100%
                    deviation_percent = ((pred_val_float - curr_val_float) / curr_val_float) * 100
                    command_value = max(-1.0, min(1.0, deviation_percent / 10))
                else:
                    command_value = Decimal("0.0")

                sensor_data[sensor_type] = {
                    "value": curr_val_sensor,
                    "pred": ml_prediction_humidity,
                    "command": Decimal(str(round(command_value, 2)))
                }

            elif sensor_type == "co2":
                if ml_prediction_co2 != Decimal("-1.0"):
                    # Преобразуем в float для вычислений
                    curr_val_float = float(curr_val_sensor)
                    pred_val_float = float(ml_prediction_co2)

                    # Для CO2 используем абсолютное отклонение (ppm)
                    deviation_absolute = pred_val_float - curr_val_float
                    command_value = max(-1.0, min(1.0, deviation_absolute / 200))
                else:
                    command_value = Decimal("0.0")

                sensor_data[sensor_type] = {
                    "value": curr_val_sensor,
                    "pred": ml_prediction_co2,
                    "command": Decimal(str(round(command_value, 2)))
                }

            elif sensor_type == "temperature":
                if ml_prediction_temperature != Decimal("-1.0"):
                    # Преобразуем в float для вычислений
                    curr_val_float = float(curr_val_sensor)
                    pred_val_float = float(ml_prediction_temperature)

                    # Абсолютное отклонение для температуры (°C)
                    deviation_absolute = pred_val_float - curr_val_float
                    command_value = max(-1.0, min(1.0, deviation_absolute / 5))
                else:
                    command_value = Decimal("0.0")

                sensor_data[sensor_type] = {
                    "value": curr_val_sensor,
                    "pred": ml_prediction_temperature,
                    "command": Decimal(str(round(command_value, 2)))
                }
            else:
                # Для других датчиков
                sensor_data[sensor_type] = {
                    "value": curr_val_sensor,
                    "pred": Decimal("-1.0"),
                    "command": Decimal("0.0")
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
            row["co2_pred"] = sensor_data["co2"]["pred"]  # 🔮 ML ПРЕДСКАЗАНИЕ CO2
            row["command_co2"] = sensor_data["co2"]["command"]

        # Сохранение в БД
        from crud.reports import create_report_db
        report_create = schemas.ReportCreate(**row)
        result = create_report_db(db, report_create)

        print(f"  ✅ Отчет создан. Предсказания - Влажность: {ml_prediction_humidity}%, CO2: {ml_prediction_co2} ppm")
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