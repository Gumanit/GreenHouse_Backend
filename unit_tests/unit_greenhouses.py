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
def sample_agrorule(test_db):
    """Создает тестовое агрономическое правило для использования в тестах"""
    rule_data = {
        "type_crop": "tomato",
        "rule_params": json.dumps({"temperature": 25})
    }
    response = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data)
    return response.json()


def test_create_greenhouse(test_db, sample_agrorule):
    """Тест создания теплицы"""
    greenhouse_data = {
        "name": "Test Greenhouse",
        "location": "Test Location",
        "description": "Test Description",
        "agrorule_id": sample_agrorule["id"]
    }

    response = client.post("/greenhouses/", json=greenhouse_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == greenhouse_data["name"]
    assert data["location"] == greenhouse_data["location"]
    assert data["description"] == greenhouse_data["description"]
    assert data["agrorule_id"] == sample_agrorule["id"]
    assert "greenhouse_id" in data


def test_create_greenhouse_with_optional_fields(test_db, sample_agrorule):
    """Тест создания теплицы с необязательными полями"""
    greenhouse_data = {
        "name": "Minimal Greenhouse",
        "agrorule_id": sample_agrorule["id"]
        # location и description не указаны
    }

    response = client.post("/greenhouses/", json=greenhouse_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == greenhouse_data["name"]
    assert data["agrorule_id"] == sample_agrorule["id"]
    assert data["location"] is None
    assert data["description"] is None


def test_get_greenhouse(test_db, sample_agrorule):
    """Тест получения теплицы по ID"""
    # Создаем теплицу
    greenhouse_data = {
        "name": "Test Greenhouse",
        "location": "Test Location",
        "description": "Test Description",
        "agrorule_id": sample_agrorule["id"]
    }
    create_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse_id = create_response.json()["greenhouse_id"]

    # Получаем теплицу
    response = client.get(f"/greenhouses/{greenhouse_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["greenhouse_id"] == greenhouse_id
    assert data["name"] == greenhouse_data["name"]
    assert data["location"] == greenhouse_data["location"]
    assert data["description"] == greenhouse_data["description"]
    assert data["agrorule_id"] == sample_agrorule["id"]


def test_get_greenhouse_not_found(test_db):
    """Тест получения несуществующей теплицы"""
    response = client.get("/greenhouses/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Greenhouse not found"


def test_get_greenhouses_list(test_db, sample_agrorule):
    """Тест получения списка теплиц"""
    # Создаем несколько теплиц
    greenhouse_data_1 = {
        "name": "Greenhouse 1",
        "location": "Location 1",
        "agrorule_id": sample_agrorule["id"]
    }
    greenhouse_data_2 = {
        "name": "Greenhouse 2",
        "location": "Location 2",
        "agrorule_id": sample_agrorule["id"]
    }

    client.post("/greenhouses/", json=greenhouse_data_1)
    client.post("/greenhouses/", json=greenhouse_data_2)

    # Получаем список
    response = client.get("/greenhouses/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(gh["name"] == "Greenhouse 1" for gh in data)
    assert any(gh["name"] == "Greenhouse 2" for gh in data)


def test_get_greenhouses_with_pagination(test_db, sample_agrorule):
    """Тест пагинации при получении списка теплиц"""
    # Создаем 3 теплицы
    for i in range(3):
        greenhouse_data = {
            "name": f"Greenhouse {i}",
            "location": f"Location {i}",
            "agrorule_id": sample_agrorule["id"]
        }
        client.post("/greenhouses/", json=greenhouse_data)

    # Тестируем лимит
    response = client.get("/greenhouses/?skip=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Тестируем skip
    response = client.get("/greenhouses/?skip=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_update_greenhouse_full(test_db, sample_agrorule):
    """Тест полного обновления теплицы"""
    # Создаем теплицу
    greenhouse_data = {
        "name": "Original Name",
        "location": "Original Location",
        "description": "Original Description",
        "agrorule_id": sample_agrorule["id"]
    }
    create_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse_id = create_response.json()["greenhouse_id"]

    # Обновляем теплицу
    update_data = {
        "name": "Updated Name",
        "location": "Updated Location",
        "description": "Updated Description",
        "agrorule_id": sample_agrorule["id"]
    }
    response = client.put(f"/greenhouses/{greenhouse_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["location"] == update_data["location"]
    assert data["description"] == update_data["description"]

def test_update_greenhouse_change_agrorule(test_db, sample_agrorule):
    """Тест изменения agrorule_id теплицы"""
    # Создаем второе агрономическое правило
    rule_data_2 = {
        "type_crop": "cucumber",
        "rule_params": json.dumps({"humidity": 60})
    }
    response_rule = client.post("/agronomic_rules/create_agronomic_rules", json=rule_data_2)
    new_agrorule = response_rule.json()

    # Создаем теплицу
    greenhouse_data = {
        "name": "Test Greenhouse",
        "location": "Test Location",
        "agrorule_id": sample_agrorule["id"]
    }
    create_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse_id = create_response.json()["greenhouse_id"]

    # Обновляем agrorule_id
    update_data = {
        "agrorule_id": new_agrorule["id"]
    }
    response = client.put(f"/greenhouses/{greenhouse_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["agrorule_id"] == new_agrorule["id"]
    assert data["name"] == greenhouse_data["name"]  # осталось прежним


def test_update_greenhouse_not_found(test_db, sample_agrorule):
    """Тест обновления несуществующей теплицы"""
    update_data = {
        "name": "Updated Name",
        "location": "Updated Location",
        "agrorule_id": sample_agrorule["id"]  # Добавляем обязательное поле
    }

    response = client.put("/greenhouses/999", json=update_data)

    assert response.status_code == 404
    assert response.json()["detail"] == "Greenhouse not found"


def test_delete_greenhouse(test_db, sample_agrorule):
    """Тест удаления теплицы"""
    # Создаем теплицу
    greenhouse_data = {
        "name": "To Delete",
        "location": "Some Location",
        "agrorule_id": sample_agrorule["id"]
    }
    create_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse_id = create_response.json()["greenhouse_id"]

    # Убеждаемся, что теплица существует
    response = client.get(f"/greenhouses/{greenhouse_id}")
    assert response.status_code == 200

    # Удаляем теплицу
    response = client.delete(f"/greenhouses/{greenhouse_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Greenhouse deleted successfully"

    # Убеждаемся, что теплицы больше нет
    response = client.get(f"/greenhouses/{greenhouse_id}")
    assert response.status_code == 404


def test_delete_greenhouse_not_found(test_db):
    """Тест удаления несуществующей теплицы"""
    response = client.delete("/greenhouses/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Greenhouse not found"
