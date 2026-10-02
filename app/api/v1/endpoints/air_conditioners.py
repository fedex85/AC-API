from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import get_db
from app.crud.crud_air_conditioner import crud_air_conditioner
from app.models.air_conditioner import ACType, EnergyRating
from app.schemas.air_conditioner import (
    AirConditionerCreate,
    AirConditionerList,
    AirConditionerResponse,
    AirConditionerUpdate,
)

router = APIRouter()


class SortField(str, Enum):
    id = "id"
    brand = "brand"
    price = "price"
    btu_capacity = "btu_capacity"
    power_consumption = "power_consumption"
    created_at = "created_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


@router.get("/", response_model=AirConditionerList)
def get_air_conditioners(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(100, ge=1, le=100, description="Registros por página"),
    brand: Optional[str] = Query(None, max_length=100, description="Marca (contiene)"),
    ac_type: Optional[ACType] = Query(None, description="Tipo de equipo"),
    energy_rating: Optional[EnergyRating] = Query(None, description="Clasificación energética"),
    min_btu: Optional[int] = Query(None, ge=0, description="BTU mínimo"),
    max_btu: Optional[int] = Query(None, ge=0, description="BTU máximo"),
    min_price: Optional[float] = Query(None, ge=0, description="Precio mínimo"),
    max_price: Optional[float] = Query(None, ge=0, description="Precio máximo"),
    available: Optional[bool] = Query(None, description="true: disponibles con stock; false: no disponibles"),
    has_inverter: Optional[bool] = Query(None),
    has_heating: Optional[bool] = Query(None),
    has_wifi: Optional[bool] = Query(None),
    sort_by: SortField = Query(SortField.id, description="Campo de ordenación"),
    order: SortOrder = Query(SortOrder.asc, description="Sentido de la ordenación"),
    db: Session = Depends(get_db),
):
    """
    Listado de aires acondicionados con filtros, ordenación y paginación.
    Todos los filtros son opcionales y se combinan entre sí.
    """
    if min_btu is not None and max_btu is not None and min_btu > max_btu:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El BTU mínimo no puede ser mayor al BTU máximo",
        )
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El precio mínimo no puede ser mayor al precio máximo",
        )

    items, total = crud_air_conditioner.get_filtered(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by.value,
        descending=order == SortOrder.desc,
        brand=brand,
        ac_type=ac_type,
        energy_rating=energy_rating,
        min_btu=min_btu,
        max_btu=max_btu,
        min_price=min_price,
        max_price=max_price,
        available=available,
        has_inverter=has_inverter,
        has_heating=has_heating,
        has_wifi=has_wifi,
    )
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{ac_id}", response_model=AirConditionerResponse)
def get_air_conditioner(ac_id: int, db: Session = Depends(get_db)):
    """Obtener un aire acondicionado específico por ID"""
    air_conditioner = crud_air_conditioner.get(db, id=ac_id)
    if not air_conditioner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aire acondicionado no encontrado",
        )
    return air_conditioner


@router.post(
    "/",
    response_model=AirConditionerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(deps.get_current_active_superuser)],
)
def create_air_conditioner(
    ac_in: AirConditionerCreate, db: Session = Depends(get_db)
):
    """Crear un nuevo aire acondicionado (solo superusuario)"""
    return crud_air_conditioner.create(db, obj_in=ac_in)


@router.patch(
    "/{ac_id}",
    response_model=AirConditionerResponse,
    dependencies=[Depends(deps.get_current_active_superuser)],
)
def update_air_conditioner(
    ac_id: int, ac_in: AirConditionerUpdate, db: Session = Depends(get_db)
):
    """
    Actualizar parcialmente un aire acondicionado (solo superusuario).
    Solo se modifican los campos enviados.
    """
    air_conditioner = crud_air_conditioner.get(db, id=ac_id)
    if not air_conditioner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aire acondicionado no encontrado",
        )
    return crud_air_conditioner.update(db, db_obj=air_conditioner, obj_in=ac_in)


@router.delete(
    "/{ac_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(deps.get_current_active_superuser)],
)
def delete_air_conditioner(ac_id: int, db: Session = Depends(get_db)):
    """Eliminar un aire acondicionado (solo superusuario)"""
    if not crud_air_conditioner.delete(db, id=ac_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aire acondicionado no encontrado",
        )
    return None
