# recreate_tables.py
from database import engine, Base
import models  # Импортируем все модели


def recreate_tables():
    print("Удаление существующих таблиц...")
    Base.metadata.drop_all(bind=engine)

    print("Создание новых таблиц...")
    Base.metadata.create_all(bind=engine)

    print("Таблицы успешно пересозданы!")


if __name__ == "__main__":
    recreate_tables()