import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import json
from datetime import datetime
from decimal import Decimal

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
def sample_greenhouse(test_db):
    """Создает тестовую теплицу"""
    rule_data = {"type_crop": "tomato", "rule_params": json.dumps({"temperature": 25})}
    rule_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    agrorule = rule_response.json()

    greenhouse_data = {"name": "Test Greenhouse", "location": "Test Location", "agrorule_id": agrorule["id"]}
    greenhouse_response = client.post("/greenhouses/", json=greenhouse_data)
    return greenhouse_response.json()


def test_create_report(test_db, sample_greenhouse):
    """Тест создания отчета"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "co2_value": 450.50,
        "humidity_value": 65.5,
        "temperature_value": 23.5,
        "report_time": datetime.now().isoformat()
    }

    response = client.post("/reports/", json=report_data)
    assert response.status_code == 200
    data = response.json()
    assert data["greenhouse_id"] == sample_greenhouse["greenhouse_id"]
    # Сравниваем как строки или конвертируем в Decimal
    assert float(data["co2_value"]) == 450.50
    assert "id" in data


def test_read_report(test_db, sample_greenhouse):
    """Тест получения отчета по ID"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    create_response = client.post("/reports/", json=report_data)
    report_id = create_response.json()["id"]

    response = client.get(f"/reports/{report_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == report_id
    assert float(data["temperature_value"]) == 25.0


def test_read_report_not_found(test_db):
    """Тест получения несуществующего отчета"""
    response = client.get("/reports/999")
    assert response.status_code == 404


def test_read_reports_list(test_db, sample_greenhouse):
    """Тест получения списка отчетов"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    client.post("/reports/", json=report_data)

    response = client.get("/reports/?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_read_reports_filter_by_greenhouse(test_db, sample_greenhouse):
    """Тест фильтрации отчетов по теплице"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    client.post("/reports/", json=report_data)

    response = client.get(f"/reports/?greenhouse_id={sample_greenhouse['greenhouse_id']}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["greenhouse_id"] == sample_greenhouse["greenhouse_id"]


def test_read_reports_by_greenhouse(test_db, sample_greenhouse):
    """Тест получения отчетов по конкретной теплице"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    client.post("/reports/", json=report_data)

    response = client.get(f"/reports/greenhouse/{sample_greenhouse['greenhouse_id']}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["greenhouse_id"] == sample_greenhouse["greenhouse_id"]


def test_read_latest_report(test_db, sample_greenhouse):
    """Тест получения последнего отчета для теплицы"""
    report_data_1 = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    report_data_2 = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 26.0,
        "report_time": datetime.now().isoformat()
    }
    client.post("/reports/", json=report_data_1)
    client.post("/reports/", json=report_data_2)

    response = client.get(f"/reports/greenhouse/{sample_greenhouse['greenhouse_id']}/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["greenhouse_id"] == sample_greenhouse["greenhouse_id"]


def test_update_report(test_db, sample_greenhouse):
    """Тест обновления отчета"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    create_response = client.post("/reports/", json=report_data)
    report_id = create_response.json()["id"]

    update_data = {"temperature_value": 26.5}
    response = client.put(f"/reports/{report_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert float(data["temperature_value"]) == 26.5


def test_delete_report(test_db, sample_greenhouse):
    """Тест удаления отчета"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    create_response = client.post("/reports/", json=report_data)
    report_id = create_response.json()["id"]

    response = client.delete(f"/reports/{report_id}")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]


def test_delete_all_reports(test_db, sample_greenhouse):
    """Тест удаления всех отчетов"""
    report_data = {
        "greenhouse_id": sample_greenhouse["greenhouse_id"],
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }
    client.post("/reports/", json=report_data)

    response = client.delete("/reports/")
    assert response.status_code == 200
    assert "Удалено" in response.json()["message"]


def test_create_report_invalid_greenhouse(test_db):
    """Тест создания отчета с несуществующей теплицей"""
    report_data = {
        "greenhouse_id": 999,
        "temperature_value": 25.0,
        "report_time": datetime.now().isoformat()
    }

    response = client.post("/reports/", json=report_data)
    assert response.status_code == 400
    assert "Greenhouse not found" in response.json()["detail"]