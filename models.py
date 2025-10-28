from sqlalchemy import Column, Integer, String, Text, DECIMAL, DateTime, ForeignKey
from database import Base
from datetime import datetime


class Greenhouse(Base):
    __tablename__ = 'greenhouses'

    greenhouse_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    description = Column(Text)


class Sensor(Base):
    __tablename__ = 'sensors'

    sensor_id = Column(Integer, primary_key=True, autoincrement=True)
    greenhouse_id = Column(Integer, ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    type = Column(String(50), nullable=False)
    min_value = Column(DECIMAL(10, 2))
    max_value = Column(DECIMAL(10, 2))


class SensorReading(Base):
    __tablename__ = 'sensorreadings'

    reading_id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(Integer, ForeignKey('sensors.sensor_id'), nullable=False)
    value = Column(DECIMAL(12, 4), nullable=False)
    reading_time = Column(DateTime, default=datetime.now)