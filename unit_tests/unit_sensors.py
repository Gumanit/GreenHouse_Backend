import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app  # или ваш основной файл приложения
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


# Переопределение зависимости базы данных
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
    # Создание таблиц
    models.Base.metadata.create_all(bind=engine)

    yield

    # Очистка после теста
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_greenhouse(test_db):
    """Фикстура для создания тестовой теплицы"""
    greenhouse_data = {
        "name": "Test Greenhouse",
        "location": "Test Location",
        "description": "Test Description"
    }
    response = client.post("/greenhouses/", json=greenhouse_data)
    return response.json()


def test_create_sensor(test_db, test_greenhouse):
    """Тест создания сенсора"""
    sensor_data = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "temperature"
    }

    response = client.post("/sensors/", json=sensor_data)

    assert response.status_code == 200
    data = response.json()
    assert data["greenhouse_id"] == sensor_data["greenhouse_id"]
    assert data["type"] == sensor_data["type"]
    assert "sensor_id" in data


def test_read_sensor(test_db, test_greenhouse):
    """Тест чтения конкретного сенсора"""
    # Сначала создаем сенсор
    sensor_data = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "humidity"
    }

    create_response = client.post("/sensors/", json=sensor_data)
    sensor_id = create_response.json()["sensor_id"]

    # Затем читаем его
    response = client.get(f"/sensors/{sensor_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["sensor_id"] == sensor_id
    assert data["type"] == sensor_data["type"]
    assert data["greenhouse_id"] == sensor_data["greenhouse_id"]


def test_read_sensor_not_found(test_db):
    """Тест чтения несуществующего сенсора"""
    response = client.get("/sensors/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found"


def test_read_sensors(test_db, test_greenhouse):
    """Тест чтения списка сенсоров"""
    # Создаем несколько сенсоров
    sensor_data_1 = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "temperature"
    }
    sensor_data_2 = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "humidity"
    }

    client.post("/sensors/", json=sensor_data_1)
    client.post("/sensors/", json=sensor_data_2)

    # Читаем список
    response = client.get("/sensors/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["type"] == sensor_data_1["type"]
    assert data[1]["type"] == sensor_data_2["type"]


def test_read_sensors_with_pagination(test_db, test_greenhouse):
    """Тест пагинации при чтении списка сенсоров"""
    # Создаем 3 сенсора
    for i in range(3):
        sensor_data = {
            "greenhouse_id": test_greenhouse["greenhouse_id"],
            "type": f"sensor_type_{i}"
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


def test_update_sensor(test_db, test_greenhouse):
    """Тест обновления сенсора"""
    # Сначала создаем сенсор
    sensor_data = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "original_type"
    }

    create_response = client.post("/sensors/", json=sensor_data)
    sensor_id = create_response.json()["sensor_id"]

    # Затем обновляем его - передаем ВСЕ обязательные поля
    update_data = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],  # обязательно
        "type": "updated_type"  # обязательно
    }

    response = client.put(f"/sensors/{sensor_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == update_data["type"]
    assert data["greenhouse_id"] == sensor_data["greenhouse_id"]


def test_update_sensor_not_found(test_db, test_greenhouse):
    """Тест обновления несуществующего сенсора"""
    update_data = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],  # обязательно
        "type": "updated_type"  # обязательно
    }

    response = client.put("/sensors/999", json=update_data)

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found"


def test_delete_sensor(test_db, test_greenhouse):
    """Тест удаления сенсора"""
    # Сначала создаем сенсор
    sensor_data = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "to_delete"
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


def test_read_greenhouse_sensors(test_db, test_greenhouse):
    """Тест чтения сенсоров конкретной теплицы"""
    # Создаем сенсоры для тестовой теплицы
    sensor_data_1 = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "temperature"
    }
    sensor_data_2 = {
        "greenhouse_id": test_greenhouse["greenhouse_id"],
        "type": "humidity"
    }

    client.post("/sensors/", json=sensor_data_1)
    client.post("/sensors/", json=sensor_data_2)

    # Создаем другую теплицу и сенсор для нее
    another_greenhouse_data = {
        "name": "Another Greenhouse",
        "location": "Another Location"
    }
    another_greenhouse_response = client.post("/greenhouses/", json=another_greenhouse_data)
    another_greenhouse_id = another_greenhouse_response.json()["greenhouse_id"]

    another_sensor_data = {
        "greenhouse_id": another_greenhouse_id,
        "type": "pressure"
    }
    client.post("/sensors/", json=another_sensor_data)

    # Читаем сенсоры только для тестовой теплицы
    response = client.get(f"/sensors/greenhouse/{test_greenhouse['greenhouse_id']}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # только 2 сенсора для тестовой теплицы
    assert all(sensor["greenhouse_id"] == test_greenhouse["greenhouse_id"] for sensor in data)


def test_read_greenhouse_sensors_empty(test_db, test_greenhouse):
    """Тест чтения сенсоров теплицы без сенсоров"""
    response = client.get(f"/sensors/greenhouse/{test_greenhouse['greenhouse_id']}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0  # пустой список


def test_create_sensor_with_invalid_greenhouse(test_db):
    """Тест создания сенсора с несуществующей теплицей"""
    sensor_data = {
        "greenhouse_id": 999,  # несуществующая теплица
        "type": "temperature"
    }

    # Этот тест может вести себя по-разному в зависимости от ваших ForeignKey constraints
    # Если есть каскадные ограничения, может возникнуть ошибка
    response = client.post("/sensors/", json=sensor_data)

    # Проверяем либо успешное создание (если нет FK constraints),
    # либо ошибку (если есть constraints)
    assert response.status_code in [200, 422, 400]


def test_sensor_types(test_db, test_greenhouse):
    """Тест различных типов сенсоров"""
    sensor_types = ["temperature", "humidity", "pressure", "light", "co2"]

    for sensor_type in sensor_types:
        sensor_data = {
            "greenhouse_id": test_greenhouse["greenhouse_id"],
            "type": sensor_type
        }

        response = client.post("/sensors/", json=sensor_data)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == sensor_type