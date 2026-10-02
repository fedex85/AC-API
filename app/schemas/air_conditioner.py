from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.air_conditioner import ACType, EnergyRating


class AirConditionerBase(BaseModel):
    brand: str = Field(..., min_length=1, max_length=100, description="Marca del aire acondicionado")
    model: str = Field(..., min_length=1, max_length=100, description="Modelo")
    ac_type: ACType = Field(..., description="Tipo de aire acondicionado")
    btu_capacity: int = Field(..., gt=0, description="Capacidad en BTU")
    power_consumption: float = Field(..., gt=0, description="Consumo de energía en Watts")
    energy_rating: EnergyRating = Field(..., description="Clasificación energética")
    recommended_area_m2: float = Field(..., gt=0, description="Área recomendada en m²")
    has_heating: bool = Field(default=False, description="¿Tiene función de calefacción?")
    has_wifi: bool = Field(default=False, description="¿Tiene conectividad WiFi?")
    has_inverter: bool = Field(default=False, description="¿Tiene tecnología inverter?")
    price: float = Field(..., gt=0, description="Precio")
    stock_quantity: int = Field(default=0, ge=0, description="Cantidad en stock")
    is_available: bool = Field(default=True, description="¿Está disponible?")
    warranty_months: int = Field(default=12, ge=0, description="Meses de garantía")
    noise_level_db: Optional[float] = Field(None, ge=0, description="Nivel de ruido en dB")


class AirConditionerCreate(AirConditionerBase):
    pass


class AirConditionerUpdate(BaseModel):
    brand: Optional[str] = Field(None, min_length=1, max_length=100)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    ac_type: Optional[ACType] = None
    btu_capacity: Optional[int] = Field(None, gt=0)
    power_consumption: Optional[float] = Field(None, gt=0)
    energy_rating: Optional[EnergyRating] = None
    recommended_area_m2: Optional[float] = Field(None, gt=0)
    has_heating: Optional[bool] = None
    has_wifi: Optional[bool] = None
    has_inverter: Optional[bool] = None
    price: Optional[float] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_available: Optional[bool] = None
    warranty_months: Optional[int] = Field(None, ge=0)
    noise_level_db: Optional[float] = Field(None, ge=0)


class AirConditionerResponse(AirConditionerBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AirConditionerList(BaseModel):
    total: int  # total de resultados que cumplen los filtros (sin paginar)
    skip: int
    limit: int
    items: list[AirConditionerResponse]
