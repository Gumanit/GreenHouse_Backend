from sqlalchemy import String, Text, DECIMAL, func, Boolean, Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from sqlalchemy.dialects.mysql import LONGBLOB

class AgronomicRule(Base):
    __tablename__ = 'agronomic_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type_crop = Column(String(255), nullable=False)
    rule_params = Column(Text, nullable=False)

    greenhouses = relationship("Greenhouse", back_populates="agronomic_rule")


class Greenhouse(Base):
    __tablename__ = 'greenhouses'

    greenhouse_id = Column(Integer, primary_key=True, autoincrement=True)
    agrorule_id = Column(Integer, ForeignKey('agronomic_rules.id'), nullable=False)
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    description = Column(Text)

    agronomic_rule = relationship("AgronomicRule", back_populates="greenhouses")
    sensors = relationship("Sensor", back_populates="greenhouse", cascade="all, delete-orphan")
    cameras = relationship("Camera", back_populates="greenhouse", cascade="all, delete-orphan")
    execution_devices = relationship("ExecutionDevice", back_populates="greenhouse", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="greenhouse", cascade="all, delete-orphan")


class Sensor(Base):
    __tablename__ = 'sensors'

    sensor_id = Column(Integer, primary_key=True, autoincrement=True)
    greenhouse_id = Column(Integer, ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    type = Column(String(50), nullable=False)

    greenhouse = relationship("Greenhouse", back_populates="sensors")
    execution_devices = relationship("ExecutionDevice", back_populates="sensor")


class ExecutionDevice(Base):
    __tablename__ = 'execution_devices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    greenhouse_id = Column(Integer, ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    sensor_id = Column(Integer, ForeignKey('sensors.sensor_id'), nullable=False)
    type = Column(String(255), nullable=False)

    greenhouse = relationship("Greenhouse", back_populates="execution_devices")
    sensor = relationship("Sensor", back_populates="execution_devices")


class Report(Base):
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    greenhouse_id = Column(Integer, ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    co2_value = Column(DECIMAL(10, 2))
    humidity_value = Column(DECIMAL(10, 2))
    temperature_value = Column(DECIMAL(10, 2))
    co2_pred = Column(DECIMAL(10, 2))
    humidity_pred = Column(DECIMAL(10, 2))
    temperature_pred = Column(DECIMAL(10, 2))
    command_co2 = Column(DECIMAL(10, 2))
    command_humidity = Column(DECIMAL(10, 2))
    command_temperature = Column(DECIMAL(10, 2))
    report_time = Column(DateTime(timezone=True), server_default=func.now())

    greenhouse = relationship("Greenhouse", back_populates="reports")


class Camera(Base):
    __tablename__ = 'cameras'

    id = Column(Integer, primary_key=True, autoincrement=True)
    greenhouse_id = Column(Integer, ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    status = Column(String(50), default="active")

    greenhouse = relationship("Greenhouse", back_populates="cameras")


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    login = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    is_sudo = Column(Boolean, nullable=False)
    description = Column(String(100))


class Detection(Base):
    __tablename__ = 'detections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    photo = Column(LONGBLOB, nullable=False)
    detection_photo = Column(LONGBLOB, nullable=False)
    greenhouse_id = Column(Integer, ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    confidence_level = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())