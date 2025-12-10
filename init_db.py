import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import AgronomicRule, Greenhouse, Sensor, ExecutionDevice

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.post("/reset_db", status_code=200)
def reset_database(db: Session = Depends(get_db)):
    """Сброс базы данных с заполнением начальными данными"""
    try:
        clear_and_seed_db(db)
        return {"message": "База данных успешно очищена и заполнена начальными данными."}
    except Exception as e:
        print(f"Ошибка при сбросе базы данных: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при сбросе базы данных: {str(e)}"
        )


def clear_and_seed_db(db: Session):
    try:
        print("Начало очистки и заполнения базы данных...")

        # Отключаем проверку внешних ключей
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        # Очищаем таблицы в правильном порядке (от дочерних к родительским)
        tables_to_clear = [
            "reports", "sensors", "cameras", "execution_devices",
            "greenhouses", "agronomic_rules", "users", "detections"
        ]

        for table in tables_to_clear:
            try:
                db.execute(text(f"DELETE FROM {table}"))
                db.execute(text(f"ALTER TABLE {table} AUTO_INCREMENT = 1"))
                print(f"Таблица {table} очищена и автоинкремент сброшен")
            except Exception as e:
                print(f"Ошибка при очистке таблицы {table}: {e}")
                raise

        # Включаем обратно проверку внешних ключей
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

        # НАЧАЛО ТРАНЗАКЦИИ ДЛЯ ЗАПОЛНЕНИЯ ДАННЫХ
        try:
            # 1. Добавляем агрономические правила
            agronomic_rules_data = [
                {"type_crop": "Огурцы", "rule_params": {"humidity": 50, "temperature": 25, "co2": 800}},
                {"type_crop": "Помидоры", "rule_params": {"humidity": 30, "temperature": 23, "co2": 700}},
                {"type_crop": "Виноград", "rule_params": {"humidity": 40, "temperature": 28, "co2": 600}},
                {"type_crop": "Капуста", "rule_params": {"humidity": 10, "temperature": 18, "co2": 500}},
                {"type_crop": "Морковь", "rule_params": {"humidity": 60, "temperature": 20, "co2": 400}},
            ]

            agronomic_rules = []
            for rule_data in agronomic_rules_data:
                rule_data_copy = rule_data.copy()
                rule_data_copy["rule_params"] = json.dumps(rule_data["rule_params"], ensure_ascii=False)
                rule = AgronomicRule(**rule_data_copy)
                db.add(rule)
                agronomic_rules.append(rule)

            db.flush()
            print("Агрономические правила добавлены")

            # 2. Добавляем теплицы
            greenhouses_data = [
                {"name": "Основная теплица", "location": "Участок 1",
                 "description": "Демонстрационная теплица для симуляции", "agrorule_id": 1},
                {"name": "Северная теплица", "location": "Участок 2",
                 "description": "Теплица для выращивания овощей в городских условиях", "agrorule_id": 2},
                {"name": "Южный комплекс", "location": "Участок 3",
                 "description": "Экспериментальная теплица с субтропическими культурами", "agrorule_id": 3},
                {"name": "Западный филиал", "location": "Участок 4",
                 "description": "Теплица для исследований морозоустойчивых растений", "agrorule_id": 4},
                {"name": "Восточный парник", "location": "Участок 5",
                 "description": "Теплица для адаптации дальневосточных сортов", "agrorule_id": 5},
            ]

            greenhouses = []
            for greenhouse_data in greenhouses_data:
                greenhouse = Greenhouse(**greenhouse_data)
                db.add(greenhouse)
                greenhouses.append(greenhouse)

            db.flush()
            print("Теплицы добавлены")

            # 3. Добавляем сенсоры с ЗНАЧЕНИЯМИ
            sensor_types = ["temperature", "humidity", "co2"]

            # Значения по умолчанию для каждого типа сенсора
            default_values = {
                "temperature": 22.5,
                "humidity": 45.0,
                "co2": 600.0
            }

            for greenhouse in greenhouses:
                for sensor_type in sensor_types:
                    sensor = Sensor(
                        greenhouse_id=greenhouse.greenhouse_id,
                        type=sensor_type,
                    )
                    db.add(sensor)

            print("Сенсоры добавлены")

            # 4. Добавляем исполнительные устройства
            execution_devices_data = [
                # Теплица 1: сенсоры с ID 1-3 (temperature=1, humidity=2, co2=3)
                {"greenhouse_id": 1, "sensor_id": 1, "type": "temperature_controller"},
                {"greenhouse_id": 1, "sensor_id": 2, "type": "humidity_controller"},
                {"greenhouse_id": 1, "sensor_id": 3, "type": "co2_controller"},

                # Теплица 2: сенсоры с ID 4-6
                {"greenhouse_id": 2, "sensor_id": 4, "type": "temperature_controller"},
                {"greenhouse_id": 2, "sensor_id": 5, "type": "humidity_controller"},
                {"greenhouse_id": 2, "sensor_id": 6, "type": "co2_controller"},

                # Теплица 3: сенсоры с ID 7-9
                {"greenhouse_id": 3, "sensor_id": 7, "type": "temperature_controller"},
                {"greenhouse_id": 3, "sensor_id": 8, "type": "humidity_controller"},
                {"greenhouse_id": 3, "sensor_id": 9, "type": "co2_controller"},

                # Теплица 4: сенсоры с ID 10-12
                {"greenhouse_id": 4, "sensor_id": 10, "type": "temperature_controller"},
                {"greenhouse_id": 4, "sensor_id": 11, "type": "humidity_controller"},
                {"greenhouse_id": 4, "sensor_id": 12, "type": "co2_controller"},

                # Теплица 5: сенсоры с ID 13-15
                {"greenhouse_id": 5, "sensor_id": 13, "type": "temperature_controller"},
                {"greenhouse_id": 5, "sensor_id": 14, "type": "humidity_controller"},
                {"greenhouse_id": 5, "sensor_id": 15, "type": "co2_controller"},
            ]

            for device_data in execution_devices_data:
                device = ExecutionDevice(**device_data)
                db.add(device)

            db.flush()
            print("Исполнительные устройства добавлены")

            # Финальный коммит всех изменений
            db.commit()
            print("Все изменения сохранены в базе данных")
            print("База данных успешно очищена и заполнена начальными данными!")

        except Exception as e:
            db.rollback()
            print(f"Ошибка при заполнении данных: {e}")
            raise

    except Exception as e:
        try:
            db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        except:
            pass
        db.rollback()
        print(f"Ошибка при инициализации БД: {e}")
        raise