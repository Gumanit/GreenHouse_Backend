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


def test_create_agronomic_rule(test_db):
    """Тест создания агрономического правила"""
    rule_data = {
        "type_crop": "tomato",
        "rule_params": json.dumps({
            "min_temperature": 15,
            "max_temperature": 30,
            "optimal_humidity": 70
        })
    }

    response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)

    assert response.status_code == 200
    data = response.json()
    assert data["type_crop"] == "tomato"
    assert "id" in data


def test_get_agronomic_rule(test_db):
    """Тест получения агрономического правила по ID"""
    # Создаем правило
    rule_data = {
        "type_crop": "cucumber",
        "rule_params": json.dumps({"threshold": 25})
    }
    create_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    rule_id = create_response.json()["id"]

    # Получаем правило
    response = client.get(f"/agronomic_rules/get_agronomic_rule/{rule_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == rule_id
    assert data["type_crop"] == "cucumber"


def test_get_agronomic_rule_not_found(test_db):
    """Тест получения несуществующего правила"""
    response = client.get("/agronomic_rules/get_agronomic_rule/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agronomic rule doesn't exist"


def test_get_agronomic_rules_list(test_db):
    """Тест получения списка агрономических правил"""
    # Создаем два правила
    rule_data_1 = {
        "type_crop": "tomato",
        "rule_params": json.dumps({"amount": 100})
    }
    rule_data_2 = {
        "type_crop": "cucumber",
        "rule_params": json.dumps({"threshold": 25})
    }

    client.post("/agronomic_rules/create_agronomic_rules", json=rule_data_1)
    client.post("/agronomic_rules/create_agronomic_rules", json=rule_data_2)

    # Получаем список
    response = client.get("/agronomic_rules/get_agronomic_rules")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["type_crop"] in ["tomato", "cucumber"]
    assert data[1]["type_crop"] in ["tomato", "cucumber"]


def test_update_agronomic_rule(test_db):
    """Тест обновления агрономического правила"""
    # Создаем правило
    rule_data = {
        "type_crop": "original_crop",
        "rule_params": json.dumps({"amount": 100})
    }
    create_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    rule_id = create_response.json()["id"]

    # Обновляем правило
    update_data = {
        "type_crop": "updated_crop",
        "rule_params": json.dumps({"threshold": 30})
    }
    response = client.put(f"/agronomic_rules/update/{rule_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["type_crop"] == "updated_crop"


def test_delete_agronomic_rule(test_db):
    """Тест удаления агрономического правила"""
    # Создаем правило
    rule_data = {
        "type_crop": "crop_to_delete",
        "rule_params": json.dumps({"amount": 100})
    }
    create_response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    rule_id = create_response.json()["id"]

    # Удаляем правило
    response = client.delete(f"/agronomic_rules/delete/{rule_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Agronomic rule deleted successfully"

    # Проверяем, что правило удалено
    response = client.get(f"/agronomic_rules/get_agronomic_rule/{rule_id}")
    assert response.status_code == 404


def test_delete_agronomic_rule_not_found(test_db):
    """Тест удаления несуществующего правила"""
    response = client.delete("/agronomic_rules/delete/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agronomic rule doesn't exist"