"""Crea (o promociona) el primer superusuario.

Uso, desde la raíz del proyecto y con el entorno virtual activado:
    python create_superuser.py

Requiere que las tablas existan (alembic upgrade head).
"""
import getpass
import sys

from pydantic import TypeAdapter, ValidationError
from pydantic import EmailStr

from app.crud import user as crud_user
from app.db.base import Base  # noqa: F401  (registra todos los modelos)
from app.db.session import SessionLocal
from app.schemas.user import UserCreate


def main() -> int:
    email_raw = input("Email del superusuario: ").strip()
    try:
        email = TypeAdapter(EmailStr).validate_python(email_raw)
    except ValidationError:
        print("Email no válido.")
        return 1

    db = SessionLocal()
    try:
        existing = crud_user.get_user_by_email(db, email=email)
        if existing:
            if existing.is_superuser:
                print("Ese usuario ya es superusuario. No se hace nada.")
                return 0
            answer = input("El usuario ya existe. ¿Convertirlo en superusuario? [s/N]: ")
            if answer.strip().lower() != "s":
                print("Cancelado.")
                return 0
            existing.is_superuser = True
            existing.is_active = True
            db.add(existing)
            db.commit()
            print(f"Usuario {email} promovido a superusuario.")
            return 0

        full_name = input("Nombre completo (opcional): ").strip() or None
        password = getpass.getpass("Contraseña (8-72 caracteres): ")
        if password != getpass.getpass("Repite la contraseña: "):
            print("Las contraseñas no coinciden.")
            return 1
        try:
            user_in = UserCreate(email=email, password=password, full_name=full_name)
        except ValidationError as exc:
            print("Datos no válidos:", exc.errors()[0]["msg"])
            return 1

        crud_user.create_user(db, user=user_in, is_superuser=True, is_active=True)
        print(f"Superusuario {email} creado correctamente.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
