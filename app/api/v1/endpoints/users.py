from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import user as crud_user
from app.models.user import User
from app.schemas.user import User as UserSchema, UserCreate

router = APIRouter()


@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    *,
    db: Annotated[Session, Depends(deps.get_db)],
    user_in: UserCreate,
):
    """
    Registra un nuevo usuario en el sistema.
    
    Validaciones:
    - El email debe ser único
    - La contraseña será hasheada automáticamente
    """
    # Verificar si el email ya está registrado
    user = crud_user.get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este email ya está registrado en el sistema",
        )
    
    # Crear el usuario
    user = crud_user.create_user(db=db, user=user_in)
    return user


@router.get("/me", response_model=UserSchema)
def read_user_me(
    current_user: Annotated[User, Depends(deps.get_current_user)],
):
    """
    Obtiene la información del usuario autenticado actual.
    """
    return current_user


@router.get("/{user_id}", response_model=UserSchema)
def read_user_by_id(
    user_id: int,
    current_user: Annotated[User, Depends(deps.get_current_user)],
    db: Annotated[Session, Depends(deps.get_db)],
):
    """
    Obtiene un usuario por ID.
    Solo usuarios autenticados pueden consultar otros usuarios.
    """
    user = crud_user.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    
    # Validar que solo superusuarios o el mismo usuario puedan ver los datos
    if user.id != current_user.id and not crud_user.is_superuser(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a este usuario",
        )
    
    return user
