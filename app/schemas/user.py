from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


# Registro público: NO incluye is_active ni is_superuser (los fija el servidor)
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: Optional[str] = None


# Actualización (uso administrativo)
class UserUpdate(UserBase):
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


# Respuesta al cliente (nunca incluye la contraseña)
class User(UserBase):
    id: int
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False

    model_config = ConfigDict(from_attributes=True)
