from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.air_conditioner import ACType, AirConditioner, EnergyRating
from app.schemas.air_conditioner import AirConditionerCreate, AirConditionerUpdate

# Columnas por las que se puede ordenar (lista blanca)
SORT_COLUMNS = {
    "id": AirConditioner.id,
    "brand": AirConditioner.brand,
    "price": AirConditioner.price,
    "btu_capacity": AirConditioner.btu_capacity,
    "power_consumption": AirConditioner.power_consumption,
    "created_at": AirConditioner.created_at,
}

# Única columna que admite NULL al actualizar
NULLABLE_FIELDS = {"noise_level_db"}


LIKE_ESCAPE = "/"  # carácter de escape sin ambigüedades entre bases de datos


def _escape_like(value: str) -> str:
    """Escapa los comodines de LIKE para que '%' y '_' se busquen literalmente."""
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


class CRUDAirConditioner:

    def get(self, db: Session, id: int) -> Optional[AirConditioner]:
        """Obtener un aire acondicionado por ID"""
        return db.query(AirConditioner).filter(AirConditioner.id == id).first()

    def _apply_filters(
        self,
        query: Query,
        *,
        brand: Optional[str] = None,
        ac_type: Optional[ACType] = None,
        energy_rating: Optional[EnergyRating] = None,
        min_btu: Optional[int] = None,
        max_btu: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        available: Optional[bool] = None,
        has_inverter: Optional[bool] = None,
        has_heating: Optional[bool] = None,
        has_wifi: Optional[bool] = None,
    ) -> Query:
        if brand:
            query = query.filter(
                AirConditioner.brand.ilike(f"%{_escape_like(brand)}%", escape=LIKE_ESCAPE)
            )
        if ac_type is not None:
            query = query.filter(AirConditioner.ac_type == ac_type)
        if energy_rating is not None:
            query = query.filter(AirConditioner.energy_rating == energy_rating)
        if min_btu is not None:
            query = query.filter(AirConditioner.btu_capacity >= min_btu)
        if max_btu is not None:
            query = query.filter(AirConditioner.btu_capacity <= max_btu)
        if min_price is not None:
            query = query.filter(AirConditioner.price >= min_price)
        if max_price is not None:
            query = query.filter(AirConditioner.price <= max_price)
        if available is True:
            query = query.filter(
                AirConditioner.is_available.is_(True),
                AirConditioner.stock_quantity > 0,
            )
        elif available is False:
            query = query.filter(
                or_(
                    AirConditioner.is_available.is_(False),
                    AirConditioner.stock_quantity.is_(None),
                    AirConditioner.stock_quantity <= 0,
                )
            )
        if has_inverter is not None:
            query = query.filter(AirConditioner.has_inverter.is_(has_inverter))
        if has_heating is not None:
            query = query.filter(AirConditioner.has_heating.is_(has_heating))
        if has_wifi is not None:
            query = query.filter(AirConditioner.has_wifi.is_(has_wifi))
        return query

    def get_filtered(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "id",
        descending: bool = False,
        **filters,
    ) -> Tuple[List[AirConditioner], int]:
        """Listado con filtros, orden y paginación. Devuelve (items, total)."""
        query = self._apply_filters(db.query(AirConditioner), **filters)
        total = query.count()

        column = SORT_COLUMNS.get(sort_by, AirConditioner.id)
        order = column.desc() if descending else column.asc()
        # Segundo criterio por id: paginación estable aunque haya valores iguales
        items = (
            query.order_by(order, AirConditioner.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def create(
        self, db: Session, obj_in: AirConditionerCreate
    ) -> AirConditioner:
        """Crear un nuevo aire acondicionado"""
        db_obj = AirConditioner(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        db_obj: AirConditioner,
        obj_in: AirConditionerUpdate,
    ) -> AirConditioner:
        """Actualizar parcialmente un aire acondicionado"""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            # Un null explícito en un campo obligatorio se ignora (si no, la BD
            # lo rechazaría con un error 500)
            if value is None and field not in NULLABLE_FIELDS:
                continue
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> Optional[AirConditioner]:
        """Eliminar un aire acondicionado"""
        obj = db.query(AirConditioner).filter(AirConditioner.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj


crud_air_conditioner = CRUDAirConditioner()
