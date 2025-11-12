from pydantic import BaseModel, ConfigDict, condecimal, Field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal, Dict, Any

'''
Схемы для Greenhouse
'''

class GreenhouseBase(BaseModel):
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    agrorule_id: int

class GreenhouseCreate(GreenhouseBase):
    pass

class Greenhouse(GreenhouseBase):
    greenhouse_id: int
    model_config = ConfigDict(from_attributes=True)

class GreenhouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    agrorule_id: int

'''
Схемы для Sensor
'''

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


'''
Схемы для Report
'''

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

'''
Схемы для ExecutionDevice
'''

DeviceType = Literal["ventilation", "humidifier", "co2_injector", "heater", "lighting"]

class ExecutionDeviceBase(BaseModel):
    greenhouse_id: int = Field(gt=0)
    sensor_id: int = Field(gt=0)
    type: DeviceType

class ExecutionDeviceCreate(ExecutionDeviceBase):
    pass

class ExecutionDeviceUpdate(BaseModel):
    greenhouse_id: int | None = Field(None, gt=0)
    sensor_id: int | None = Field(None, gt=0)
    type: DeviceType | None = None

class ExecutionDevice(ExecutionDeviceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

'''
Схемы для AgronomicRule
'''

class AgronomicRuleBase(BaseModel):
    type_crop: str = Field(max_length=255)
    rule_params: str

class AgronomicRuleCreate(AgronomicRuleBase):
    pass

class AgronomicRuleUpdate(BaseModel):
    type_crop: str | None = Field(None, max_length=255)
    rule_params: str | None

class AgronomicRule(AgronomicRuleBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

'''
Схемы для Camera
'''

class CameraBase(BaseModel):
    greenhouse_id: int
    status: str = Field(max_length=50)

class CameraCreate(CameraBase):
    pass

class CameraUpdate(BaseModel):
    greehouse_id: Optional[int] = None
    status: Optional[str] = Field(None, max_length=50)

class Camera(CameraBase):
    id: int
    model_config = ConfigDict(from_attributes=True)