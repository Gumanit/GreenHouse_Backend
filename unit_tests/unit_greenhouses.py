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


def test_create_greenhouse(test_db):
    """Тест создания теплицы"""
    greenhouse_data = {
        "name": "Test Greenhouse",
        "location": "Test Location",
        "description": "Test Description"
    }

    response = client.post("/greenhouses/", json=greenhouse_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == greenhouse_data["name"]
    assert data["location"] == greenhouse_data["location"]
    assert data["description"] == greenhouse_data["description"]
    assert "greenhouse_id" in data


def test_read_greenhouse(test_db):
    """Тест чтения конкретной теплицы"""
    # Сначала создаем теплицу
    greenhouse_data = {
        "name": "Test Greenhouse",
        "location": "Test Location",
        "description": "Test Description"
    }

    create_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse_id = create_response.json()["greenhouse_id"]

    # Затем читаем ее
    response = client.get(f"/greenhouses/{greenhouse_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["greenhouse_id"] == greenhouse_id
    assert data["name"] == greenhouse_data["name"]
    assert data["description"] == greenhouse_data["description"]


def test_read_greenhouse_not_found(test_db):
    """Тест чтения несуществующей теплицы"""
    response = client.get("/greenhouses/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Greenhouse not found"


def test_read_greenhouses(test_db):
    """Тест чтения списка теплиц"""
    # Создаем несколько теплиц
    greenhouse_data_1 = {
        "name": "Greenhouse 1",
        "location": "Location 1",
        "description": "Description 1"
    }
    greenhouse_data_2 = {
        "name": "Greenhouse 2",
        "location": "Location 2",
        "description": "Description 2"
    }

    client.post("/greenhouses/", json=greenhouse_data_1)
    client.post("/greenhouses/", json=greenhouse_data_2)

    # Читаем список
    response = client.get("/greenhouses/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == greenhouse_data_1["name"]
    assert data[1]["name"] == greenhouse_data_2["name"]


def test_read_greenhouses_with_pagination(test_db):
    """Тест пагинации при чтении списка теплиц"""
    # Создаем 3 теплицы
    for i in range(3):
        greenhouse_data = {
            "name": f"Greenhouse {i}",
            "location": f"Location {i}",
            "description": f"Description {i}"
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


def test_update_greenhouse(test_db):
    """Тест обновления теплицы"""
    # Сначала создаем теплицу
    greenhouse_data = {
        "name": "Original Name",
        "location": "Original Location",
        "description": "Original Description"
    }

    create_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse_id = create_response.json()["greenhouse_id"]

    # Затем обновляем ее
    update_data = {
        "name": "Updated Name",
        "location": "Updated Location",
        "description": "Updated Description"
    }

    response = client.put(f"/greenhouses/{greenhouse_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["location"] == update_data["location"]
    assert data["description"] == update_data["description"]


def test_update_greenhouse_partial(test_db):
    """Тест частичного обновления теплицы"""
    # Сначала создаем теплицу
    greenhouse_data = {
        "name": "Original Name",
        "location": "Original Location",
        "description": "Original Description"
    }

    create_response = client.post("/greenhouses/", json=greenhouse_data)
    greenhouse_id = create_response.json()["greenhouse_id"]

    # Обновляем только название
    update_data = {
        "name": "Updated Name Only"
    }

    response = client.put(f"/greenhouses/{greenhouse_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["location"] == greenhouse_data["location"]  # осталось прежним
    assert data["description"] == greenhouse_data["description"]  # осталось прежним


def test_update_greenhouse_not_found(test_db):
    """Тест обновления несуществующей теплицы"""
    update_data = {
        "name": "Updated Name",
        "location": "Updated Location"
    }

    response = client.put("/greenhouses/999", json=update_data)

    assert response.status_code == 404
    assert response.json()["detail"] == "Greenhouse not found"


def test_delete_greenhouse(test_db):
    """Тест удаления теплицы"""
    # Сначала создаем теплицу
    greenhouse_data = {
        "name": "To Delete",
        "location": "Some Location",
        "description": "Some Description"
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

#
# Sensors
#
