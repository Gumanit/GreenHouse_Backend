import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import json

from main import app
from database import get_db
import models

# Тестовая база данных в памяти
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function")
def test_db():
    models.Base.metadata.create_all(bind=engine)
    yield
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_greenhouse(test_db):
    """Создает тестовую теплицу для использования в тестах"""
    # Сначала создаем агрономическое правило
    rule_data = {
        "type_crop": "tomato",
        "rule_params": json.dumps({"temperature": 25})
    }
    rule_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    agrorule = rule_response.json()

    # Создаем теплицу
    greenhouse_data = {
        "name": "Test Greenhouse",
        "location": "Test Location",
        "agrorule_id": agrorule["id"]
    }
    greenhouse_response = client.post("/greenhouses/", json=greenhouse_data)
    return greenhouse_response.json()


def test_create_sensor(test_db, sample_greenhouse):
    """Тест создания сенсора"""
    sensor_data = {
        "type": "temperature",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }

    response = client.post("/sensors/", json=sensor_data)

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == sensor_data["type"]
    assert data["greenhouse_id"] == sample_greenhouse["greenhouse_id"]
    assert "sensor_id" in data


def test_create_sensor_different_types(test_db, sample_greenhouse):
    """Тест создания сенсоров разных типов"""
    sensor_types = ["temperature", "humidity", "light", "co2", "soil_moisture"]

    for sensor_type in sensor_types:
        sensor_data = {
            "type": sensor_type,
            "greenhouse_id": sample_greenhouse["greenhouse_id"]
        }
        response = client.post("/sensors/", json=sensor_data)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == sensor_type


def test_create_sensor_invalid_greenhouse_id(test_db):
    """Тест создания сенсора с несуществующим greenhouse_id"""
    sensor_data = {
        "type": "temperature",
        "greenhouse_id": 999  # Несуществующий ID
    }

    response = client.post("/sensors/", json=sensor_data)

    # Должна быть ошибка из-за foreign key constraint
    assert response.status_code >= 400


def test_get_sensor(test_db, sample_greenhouse):
    """Тест получения сенсора по ID"""
    # Создаем сенсор
    sensor_data = {
        "type": "humidity",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }
    create_response = client.post("/sensors/", json=sensor_data)
    sensor_id = create_response.json()["sensor_id"]

    # Получаем сенсор
    response = client.get(f"/sensors/{sensor_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["sensor_id"] == sensor_id
    assert data["type"] == sensor_data["type"]
    assert data["greenhouse_id"] == sample_greenhouse["greenhouse_id"]


def test_get_sensor_not_found(test_db):
    """Тест получения несуществующего сенсора"""
    response = client.get("/sensors/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found"


def test_get_sensors_list(test_db, sample_greenhouse):
    """Тест получения списка сенсоров"""
    # Создаем несколько сенсоров
    sensor_data_1 = {
        "type": "temperature",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }
    sensor_data_2 = {
        "type": "humidity",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }

    client.post("/sensors/", json=sensor_data_1)
    client.post("/sensors/", json=sensor_data_2)

    # Получаем список
    response = client.get("/sensors/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    sensor_types = [sensor["type"] for sensor in data]
    assert "temperature" in sensor_types
    assert "humidity" in sensor_types


def test_get_sensors_with_pagination(test_db, sample_greenhouse):
    """Тест пагинации при получении списка сенсоров"""
    # Создаем 3 сенсора
    for i in range(3):
        sensor_data = {
            "type": f"sensor_type_{i}",
            "greenhouse_id": sample_greenhouse["greenhouse_id"]
        }
        client.post("/sensors/", json=sensor_data)

    # Тестируем лимит
    response = client.get("/sensors/?skip=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Тестируем skip
    response = client.get("/sensors/?skip=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_sensors_by_greenhouse(test_db, sample_greenhouse):
    """Тест получения сенсоров конкретной теплицы"""
    # Создаем вторую теплицу
    rule_data = {
        "type_crop": "cucumber",
        "rule_params": json.dumps({"humidity": 60})
    }
    rule_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    agrorule_2 = rule_response.json()

    greenhouse_data_2 = {
        "name": "Second Greenhouse",
        "location": "Second Location",
        "agrorule_id": agrorule_2["id"]
    }
    greenhouse_response_2 = client.post("/greenhouses/", json=greenhouse_data_2)
    greenhouse_2 = greenhouse_response_2.json()

    # Создаем сенсоры для обеих теплиц
    sensor_data_1 = {
        "type": "temperature",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }
    sensor_data_2 = {
        "type": "humidity",
        "greenhouse_id": greenhouse_2["greenhouse_id"]
    }

    client.post("/sensors/", json=sensor_data_1)
    client.post("/sensors/", json=sensor_data_2)

    # Получаем список всех сенсоров
    response = client.get("/sensors/")
    assert response.status_code == 200
    all_sensors = response.json()
    assert len(all_sensors) == 2

    # Можно добавить endpoint для фильтрации по greenhouse_id, если нужно
    # response_filtered = client.get(f"/sensors/?greenhouse_id={sample_greenhouse['greenhouse_id']}")


def test_update_sensor(test_db, sample_greenhouse):
    """Тест обновления сенсора"""
    # Создаем сенсор
    sensor_data = {
        "type": "temperature",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }
    create_response = client.post("/sensors/", json=sensor_data)
    sensor_id = create_response.json()["sensor_id"]

    # Обновляем сенсор
    update_data = {
        "type": "humidity",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }
    response = client.put(f"/sensors/{sensor_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == update_data["type"]
    assert data["greenhouse_id"] == update_data["greenhouse_id"]


def test_update_sensor_change_greenhouse(test_db, sample_greenhouse):
    """Тест изменения greenhouse_id сенсора"""
    # Создаем вторую теплицу
    rule_data = {
        "type_crop": "cucumber",
        "rule_params": json.dumps({"humidity": 60})
    }
    rule_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    agrorule_2 = rule_response.json()

    greenhouse_data_2 = {
        "name": "Second Greenhouse",
        "location": "Second Location",
        "agrorule_id": agrorule_2["id"]
    }
    greenhouse_response_2 = client.post("/greenhouses/", json=greenhouse_data_2)
    greenhouse_2 = greenhouse_response_2.json()

    # Создаем сенсор
    sensor_data = {
        "type": "temperature",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }
    create_response = client.post("/sensors/", json=sensor_data)
    sensor_id = create_response.json()["sensor_id"]

    # Обновляем greenhouse_id
    update_data = {
        "type": "temperature",
        "greenhouse_id": greenhouse_2["greenhouse_id"]
    }
    response = client.put(f"/sensors/{sensor_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["greenhouse_id"] == greenhouse_2["greenhouse_id"]
    assert data["type"] == sensor_data["type"]  # тип остался прежним


def test_update_sensor_not_found(test_db, sample_greenhouse):
    """Тест обновления несуществующего сенсора"""
    update_data = {
        "type": "updated_type",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }

    response = client.put("/sensors/999", json=update_data)

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found"


def test_delete_sensor(test_db, sample_greenhouse):
    """Тест удаления сенсора"""
    # Создаем сенсор
    sensor_data = {
        "type": "temperature",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }
    create_response = client.post("/sensors/", json=sensor_data)
    sensor_id = create_response.json()["sensor_id"]

    # Убеждаемся, что сенсор существует
    response = client.get(f"/sensors/{sensor_id}")
    assert response.status_code == 200

    # Удаляем сенсор
    response = client.delete(f"/sensors/{sensor_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Sensor deleted successfully"

    # Убеждаемся, что сенсора больше нет
    response = client.get(f"/sensors/{sensor_id}")
    assert response.status_code == 404


def test_delete_sensor_not_found(test_db):
    """Тест удаления несуществующего сенсора"""
    response = client.delete("/sensors/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found"


def test_sensor_type_required(test_db, sample_greenhouse):
    """Тест что поле type обязательно"""
    sensor_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
        # type отсутствует
    }

    response = client.post("/sensors/", json=sensor_data)

    assert response.status_code == 422  # Validation error


def test_sensor_greenhouse_id_required(test_db):
    """Тест что поле greenhouse_id обязательно"""
    sensor_data = {
        "type": "temperature"
        # greenhouse_id отсутствует
    }

    response = client.post("/sensors/", json=sensor_data)

    assert response.status_code == 422  # Validation error


def test_sensor_type_max_length(test_db, sample_greenhouse):
    """Тест максимальной длины type (50 символов)"""
    # Допустимая длина
    valid_sensor_data = {
        "type": "a" * 50,  # максимальная длина
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }

    response = client.post("/sensors/", json=valid_sensor_data)
    assert response.status_code == 200

    # Слишком длинная строка (должна вернуть ошибку валидации)
    invalid_sensor_data = {
        "type": "a" * 51,  # превышает максимальную длину
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }

    response = client.post("/sensors/", json=invalid_sensor_data)
    assert response.status_code == 422  # Validation error


def test_create_multiple_sensors_same_greenhouse(test_db, sample_greenhouse):
    """Тест создания нескольких сенсоров для одной теплицы"""
    sensor_data_1 = {
        "type": "temperature",
        "greenhouse_id": sample_greenhouse["greenhouse_id"]
    }

    sensor_data_2 = {
        "type": "humidity",  # другой тип
        "greenhouse_id": sample_greenhouse["greenhouse_id"]  # та же теплица
    }

    response_1 = client.post("/sensors/", json=sensor_data_1)
    response_2 = client.post("/sensors/", json=sensor_data_2)

    assert response_1.status_code == 200
    assert response_2.status_code == 200

    # Оба сенсора должны быть созданы с разными ID
    data_1 = response_1.json()
    data_2 = response_2.json()

    assert data_1["sensor_id"] != data_2["sensor_id"]
    assert data_1["greenhouse_id"] == data_2["greenhouse_id"] == sample_greenhouse["greenhouse_id"]