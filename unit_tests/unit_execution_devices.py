import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import json

from main import app
from database import get_db
import models

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
def sample_setup(test_db):
    """Создает тестовые данные"""
    rule_data = {"type_crop": "tomato", "rule_params": json.dumps({"temperature": 25})}
    rule_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    agrorule = rule_response.json()

    greenhouse_data = {"name": "Test Greenhouse", "location": "Test Location", "agrorule_id": agrorule["id"]}
    greenhouse_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse = greenhouse_response.json()

    sensor_data = {"type": "temperature", "greenhouse_id": greenhouse["greenhouse_id"]}
    sensor_response = client.post("/sensors/", json=sensor_data)
    sensor = sensor_response.json()

    return {"greenhouse": greenhouse, "sensor": sensor}


def test_create_execution_device(test_db, sample_setup):
    """Тест создания устройства"""
    device_data = {
        "greenhouse_id": sample_setup["greenhouse"]["greenhouse_id"],
        "sensor_id": sample_setup["sensor"]["sensor_id"],
        "type": "ventilation"
    }
    response = client.post("/execution_devices/create", json=device_data)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "ventilation"
    assert "id" in data


def test_read_execution_device(test_db, sample_setup):
    """Тест получения устройства"""
    device_data = {
        "greenhouse_id": sample_setup["greenhouse"]["greenhouse_id"],
        "sensor_id": sample_setup["sensor"]["sensor_id"],
        "type": "heater"
    }
    create_response = client.post("/execution_devices/create", json=device_data)
    device_id = create_response.json()["id"]

    response = client.get(f"/execution_devices/read/{device_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == device_id
    assert data["type"] == "heater"


def test_read_execution_device_not_found(test_db):
    """Тест получения несуществующего устройства"""
    response = client.get("/execution_devices/read/999")
    assert response.status_code == 404


def test_read_execution_devices_list(test_db, sample_setup):
    """Тест получения списка устройств"""
    device_data = {
        "greenhouse_id": sample_setup["greenhouse"]["greenhouse_id"],
        "sensor_id": sample_setup["sensor"]["sensor_id"],
        "type": "ventilation"
    }
    client.post("/execution_devices/create", json=device_data)

    response = client.get("/execution_devices/read?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_update_execution_device(test_db, sample_setup):
    """Тест обновления устройства"""
    device_data = {
        "greenhouse_id": sample_setup["greenhouse"]["greenhouse_id"],
        "sensor_id": sample_setup["sensor"]["sensor_id"],
        "type": "ventilation"
    }
    create_response = client.post("/execution_devices/create", json=device_data)
    device_id = create_response.json()["id"]

    update_data = {"type": "heater"}
    response = client.put(f"/execution_devices/update/{device_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "heater"


def test_delete_execution_device(test_db, sample_setup):
    """Тест удаления устройства"""
    device_data = {
        "greenhouse_id": sample_setup["greenhouse"]["greenhouse_id"],
        "sensor_id": sample_setup["sensor"]["sensor_id"],
        "type": "ventilation"
    }
    create_response = client.post("/execution_devices/create", json=device_data)
    device_id = create_response.json()["id"]

    response = client.delete(f"/execution_devices/delete/{device_id}")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]


def test_validation_required_fields(test_db):
    """Тест валидации обязательных полей"""
    device_data = {}  # Все поля отсутствуют
    response = client.post("/execution_devices/create", json=device_data)
    assert response.status_code == 422


def test_validation_device_type(test_db, sample_setup):
    """Тест валидации типа устройства"""
    device_data = {
        "greenhouse_id": sample_setup["greenhouse"]["greenhouse_id"],
        "sensor_id": sample_setup["sensor"]["sensor_id"],
        "type": "invalid_type"
    }
    response = client.post("/execution_devices/create", json=device_data)
    assert response.status_code == 422