from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum
from sqlalchemy.sql import func
import enum
from app.db.session import Base


class ACType(str, enum.Enum):
    SPLIT = "split"
    WINDOW = "window"
    PORTABLE = "portable"
    CENTRAL = "central"
    MINI_SPLIT = "mini_split"


class EnergyRating(str, enum.Enum):
    A_PLUS_PLUS_PLUS = "A+++"
    A_PLUS_PLUS = "A++"
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class AirConditioner(Base):
    __tablename__ = "air_conditioners"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False)
    ac_type = Column(Enum(ACType), nullable=False)
    
    # Capacidad en BTU (British Thermal Units)
    btu_capacity = Column(Integer, nullable=False)
    
    # Potencia en Watts
    power_consumption = Column(Float, nullable=False)
    
    # Clasificación energética
    energy_rating = Column(Enum(EnergyRating), nullable=False)
    
    # Área recomendada en metros cuadrados
    recommended_area_m2 = Column(Float, nullable=False)
    
    # Características
    has_heating = Column(Boolean, default=False)
    has_wifi = Column(Boolean, default=False)
    has_inverter = Column(Boolean, default=False)
    
    # Precio y disponibilidad
    price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, default=0)
    is_available = Column(Boolean, default=True)
    
    # Información adicional
    warranty_months = Column(Integer, default=12)
    noise_level_db = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AirConditioner {self.brand} {self.model}>"
