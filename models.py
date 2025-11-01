from sqlalchemy import Column, Integer, String, Text, DECIMAL, DateTime, ForeignKey, func
from database import Base


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

class Report(Base):
    __tablename__ = 'reports'
    id = Column(Integer, primary_key=True, autoincrement=True)
    greenhouse_id = Column(Integer, ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    co2_value = Column(DECIMAL(10,2))
    humidity_value = Column(DECIMAL(10,2))
    temperature_value = Column(DECIMAL(10,2))
    co2_pred = Column(DECIMAL(10,2))
    humidity_pred = Column(DECIMAL(10,2))
    temperature_pred = Column(DECIMAL(10,2))
    command_co2 = Column(DECIMAL(10,2))
    command_humidity = Column(DECIMAL(10,2))
    command_temperature = Column(DECIMAL(10,2))
    report_time = Column(DateTime(timezone=True), server_default=func.now())