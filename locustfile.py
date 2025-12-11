import random

from locust import HttpUser, task, between

class FastAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task(4)
    def get_all_greenhouses(self):
        """GET /greenhouses/"""
        limit = random.choice([10, 50, 100, 500])
        self.client.get(f"/greenhouses/?skip=0&limit={limit}")

    @task(3)
    def create_greenhouse(self):
        """POST /greenhouses/"""
        payload = {
            "name": "Тестируемая теплица",
            "location": "Уфа",
            "description": "Это тест",
            "agrorule_id": random.randint(1,5)
        }

        self.client.post("/greenhouses/", json=payload)

