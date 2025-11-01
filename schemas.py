from pydantic import BaseModel, ConfigDict, condecimal
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

# Схемы для Greenhouse
class GreenhouseBase(BaseModel):
    name: str
    location: Optional[str] = None
    description: Optional[str] = None

class GreenhouseCreate(GreenhouseBase):
    pass

class Greenhouse(GreenhouseBase):
    greenhouse_id: int
    model_config = ConfigDict(from_attributes=True)

class GreenhouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

# Схемы для Sensor
class SensorBase(BaseModel):
    type: str
    greenhouse_id: int

class SensorCreate(SensorBase):
    pass

class Sensor(SensorBase):
    sensor_id: int
    model_config = ConfigDict(from_attributes=True)

class SensorUpdate(BaseModel):
    type: str
    greenhouse_id: int

# Схемы для Report
class ReportBase(BaseModel):
    greenhouse_id: int
    co2_value: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    humidity_value: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    temperature_value: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    co2_pred: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    humidity_pred: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    temperature_pred: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    command_co2: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    command_humidity: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    command_temperature: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    report_time: datetime



class ReportCreate(ReportBase):
    """Схема для создания нового отчета"""
    pass


class ReportUpdate(BaseModel):
    """Схема для частичного обновления"""
    co2_value: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    humidity_value: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    temperature_value: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    co2_pred: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    humidity_pred: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    temperature_pred: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    command_co2: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    command_humidity: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    command_temperature: Optional[condecimal(max_digits=10, decimal_places=2)] = None


class ReportRead(ReportBase):
    """Схема для отображения данных"""
    id: int
    report_time: datetime