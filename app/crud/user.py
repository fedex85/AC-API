from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


def get_user(db: Session, user_id: int) -> Optional[User]:
    """
    Obtiene un usuario por su ID.
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Obtiene un usuario por su email.
    Útil para login y verificar si el email ya está registrado.
    """
    return db.query(User).filter(User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """
    Obtiene una lista de usuarios con paginación.
    """
    return db.query(User).offset(skip).limit(limit).all()


def create_user(
    db: Session,
    user: UserCreate,
    *,
    is_superuser: bool = False,
    is_active: bool = True,
) -> User:
    """
    Crea un nuevo usuario en la base de datos.
    - Hashea la contraseña antes de almacenarla.
    - is_superuser / is_active los decide el servidor, nunca el cliente.
    - Devuelve el usuario creado.
    """
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        is_active=is_active,
        is_superuser=is_superuser,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)  # Actualiza el objeto con los datos de la DB (ej: ID)
    return db_user


def update_user(db: Session, db_user: User, user_update: UserUpdate) -> User:
    """
    Actualiza los datos de un usuario existente.
    Solo actualiza los campos que se proporcionan (no None).
    """
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Si se proporciona una nueva contraseña, la hasheamos
    if "password" in update_data:
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> Optional[User]:
    """
    Elimina un usuario de la base de datos.
    Devuelve el usuario eliminado o None si no existe.
    """
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user


_dummy_hash: Optional[str] = None


def _get_dummy_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = get_password_hash("contraseña-ficticia")
    return _dummy_hash


def authenticate(db: Session, email: str, password: str) -> Optional[User]:
    """
    Autentica un usuario verificando email y contraseña.
    Devuelve el usuario si las credenciales son correctas, None en caso contrario.
    """
    user = get_user_by_email(db, email=email)
    if not user:
        # Verifica contra un hash ficticio para que el tiempo de respuesta sea
        # similar y no se pueda averiguar qué emails existen.
        verify_password(password, _get_dummy_hash())
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def is_active(user: User) -> bool:
    """
    Verifica si un usuario está activo.
    """
    return bool(user.is_active)


def is_superuser(user: User) -> bool:
    """
    Verifica si un usuario es superusuario.
    """
    return bool(user.is_superuser)
