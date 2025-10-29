from pydantic import BaseModel, ConfigDict
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

# Схемы для SensorReading
class SensorReadingBase(BaseModel):
    sensor_id: int
    value: Decimal
    reading_time: Optional[datetime] = None

class SensorReadingCreate(SensorReadingBase):
    pass

class SensorReading(SensorReadingBase):
    reading_id: int
    model_config = ConfigDict(from_attributes=True)

class SensorReadingUpdate(BaseModel):
    value: Optional[Decimal] = None