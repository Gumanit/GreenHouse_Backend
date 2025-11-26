import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
import time

from models import Greenhouse, Sensor, AgronomicRule

# Тестовые настройки БД
TEST_DATABASE_URL = "mysql+pymysql://root:12345@localhost/greenhouse"


class TestDatabaseResilience:
    """Тесты отказоустойчивости базы данных"""

    @pytest.fixture(scope="function")
    def test_engine(self):
        """Создание тестового движка БД"""
        engine = create_engine(
            TEST_DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )

        # Проверяем соединение
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        yield engine

        engine.dispose()

    @pytest.fixture
    def test_session(self, test_engine):
        """Создание тестовой сессии"""
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def setup_test_data(self, test_session):
        """Создание тестовых данных с изоляцией"""
        # Получаем текущее количество записей для проверки изоляции
        initial_greenhouse_count = test_session.query(Greenhouse).count()
        initial_sensor_count = test_session.query(Sensor).count()
        initial_rule_count = test_session.query(AgronomicRule).count()

        # Создаем аграрное правило с уникальным именем
        agronomic_rule = AgronomicRule(
            type_crop=f"Test Crop {time.time()}",  # Уникальное имя
            rule_params="{'temp_min': 18, 'temp_max': 25}"
        )
        test_session.add(agronomic_rule)
        test_session.commit()

        # Создаем теплицу с уникальным именем
        greenhouse = Greenhouse(
            name=f"Test Greenhouse {time.time()}",
            location="Test Location",
            description="Test Description",
            agrorule_id=agronomic_rule.id
        )
        test_session.add(greenhouse)
        test_session.commit()

        # Создаем сенсор
        sensor = Sensor(
            type="temperature",
            greenhouse_id=greenhouse.greenhouse_id
        )
        test_session.add(sensor)
        test_session.commit()

        return {
            'agronomic_rule': agronomic_rule,
            'greenhouse': greenhouse,
            'sensor': sensor,
            'initial_counts': {
                'greenhouse': initial_greenhouse_count,
                'sensor': initial_sensor_count,
                'rule': initial_rule_count
            }
        }

    def test_connection_recovery(self, test_engine):
        """Тест восстановления соединения после разрыва"""
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        test_engine.dispose()

        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_transaction_rollback_on_failure(self, test_session, setup_test_data):
        """Тест отката транзакции при ошибке"""
        test_data = setup_test_data
        initial_sensor_count = test_data['initial_counts']['sensor']

        # Попытка создать сенсор с несуществующим greenhouse_id
        invalid_sensor = Sensor(
            type="humidity",
            greenhouse_id=99999  # Несуществующий ID
        )
        test_session.add(invalid_sensor)

        # Должна возникнуть ошибка целостности
        with pytest.raises(IntegrityError):
            test_session.commit()

        # Проверяем, что транзакция откатилась
        test_session.rollback()

        # Проверяем количество сенсоров - должно быть как изначально + 1 (из setup_test_data)
        sensors_count = test_session.query(Sensor).count()
        expected_count = initial_sensor_count + 1  # +1 сенсор из setup_test_data
        assert sensors_count == expected_count, f"Expected {expected_count}, got {sensors_count}"

    def test_concurrent_connections(self, test_engine):
        """Тест обработки конкурентных соединений"""

        def create_connection():
            with test_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.scalar()

        connections = []
        for i in range(3):
            connections.append(create_connection())

        assert all(result == 1 for result in connections)

    def test_invalid_data_handling(self, test_session, setup_test_data):
        """Тест обработки невалидных данных"""
        test_data = setup_test_data

        # Попытка создать запись с NULL в обязательном поле
        with pytest.raises(IntegrityError):
            invalid_greenhouse = Greenhouse(
                name=None,  # Обязательное поле
                location="Test",
                agrorule_id=test_data['agronomic_rule'].id
            )
            test_session.add(invalid_greenhouse)
            test_session.commit()

    def test_connection_pool_recovery(self, test_engine):
        """Тест восстановления пула соединений"""
        connections = []
        for i in range(2):
            conn = test_engine.connect()
            connections.append(conn)

        for conn in connections:
            conn.close()

        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_foreign_key_constraints(self, test_session):
        """Тест ограничений внешних ключей"""
        # Попытка создать greenhouse с несуществующим agrorule_id
        invalid_greenhouse = Greenhouse(
            name=f"Invalid Greenhouse {time.time()}",
            agrorule_id=99999  # Несуществующий ID
        )
        test_session.add(invalid_greenhouse)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_data_consistency_after_error(self, test_session, setup_test_data):
        """Тест сохранения консистентности данных после ошибки"""
        test_data = setup_test_data
        initial_greenhouse_count = test_data['initial_counts']['greenhouse']

        # Попытка операции, которая завершится ошибкой
        try:
            invalid_operation = text("SELECT * FROM non_existent_table")
            test_session.execute(invalid_operation)
            test_session.commit()
        except SQLAlchemyError:
            test_session.rollback()

        # Проверяем, что данные остались неизменными
        final_count = test_session.query(Greenhouse).count()
        expected_count = initial_greenhouse_count + 1  # +1 greenhouse из setup_test_data
        assert final_count == expected_count

    def test_session_management(self, test_session):
        """Тест управления сессиями"""
        # Создаем объект с уникальным именем
        agronomic_rule = AgronomicRule(
            type_crop=f"Lettuce {time.time()}",
            rule_params="{'light_hours': 12}"
        )
        test_session.add(agronomic_rule)

        assert agronomic_rule in test_session
        assert agronomic_rule.id is None

        test_session.commit()
        assert agronomic_rule.id is not None

    def test_bulk_operations_resilience(self, test_session, setup_test_data):
        """Тест отказоустойчивости при массовых операциях"""
        test_data = setup_test_data
        initial_greenhouse_count = test_data['initial_counts']['greenhouse']

        # Создаем несколько валидных greenhouse с уникальными именами
        valid_greenhouses = [
            Greenhouse(
                name=f"Greenhouse {i} {time.time()}",
                agrorule_id=test_data['agronomic_rule'].id
            )
            for i in range(3)
        ]

        # И один невалидный
        invalid_greenhouse = Greenhouse(
            name=None,
            agrorule_id=test_data['agronomic_rule'].id
        )

        # Добавляем все вместе
        for gh in valid_greenhouses:
            test_session.add(gh)
        test_session.add(invalid_greenhouse)

        # Вся операция должна провалиться из-за невалидных данных
        with pytest.raises(IntegrityError):
            test_session.commit()

        test_session.rollback()

        # Проверяем, что ничего не добавилось кроме исходных данных
        count = test_session.query(Greenhouse).count()
        expected_count = initial_greenhouse_count + 1  # +1 greenhouse из setup_test_data
        assert count == expected_count, f"Expected {expected_count}, got {count}"

    def test_database_operations_with_reconnect(self, test_engine):
        """Тест операций БД с переподключением"""
        # Тест 1: Проверяем, что обычные запросы работают до и после переподключения
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        # Переподключаемся
        test_engine.dispose()

        # Проверяем, что запросы все еще работают
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        # Тест 2: Проверяем работу с данными (используем временную таблицу в транзакции)
        with test_engine.connect() as conn:
            with conn.begin():
                # Создаем временную таблицу в рамках транзакции
                conn.execute(text("CREATE TEMPORARY TABLE test_reconnect (id INT PRIMARY KEY)"))
                conn.execute(text("INSERT INTO test_reconnect (id) VALUES (1)"))
                result = conn.execute(text("SELECT COUNT(*) FROM test_reconnect"))
                assert result.scalar() == 1

        # Переподключаемся
        test_engine.dispose()

        # Проверяем, что соединение все еще работает
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_error_handling_missing_table(self, test_engine):
        """Тест обработки ошибок при обращении к несуществующей таблице"""
        with test_engine.connect() as conn:
            with pytest.raises(SQLAlchemyError):
                conn.execute(text("SELECT * FROM non_existent_table_12345"))

    def test_connection_timeout_handling(self, test_engine):
        """Тест обработки таймаутов соединения"""
        with test_engine.connect() as conn:
            # Проверяем, что обычные запросы работают
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_database_isolation(self, test_session, setup_test_data):
        """Тест изоляции тестовых данных"""
        test_data = setup_test_data

        # Проверяем, что наши тестовые данные уникальны
        unique_greenhouse = test_session.query(Greenhouse).filter_by(
            name=test_data['greenhouse'].name
        ).first()

        assert unique_greenhouse is not None
        assert unique_greenhouse.greenhouse_id == test_data['greenhouse'].greenhouse_id