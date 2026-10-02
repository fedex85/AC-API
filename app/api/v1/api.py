from fastapi import APIRouter, Depends

from app.api import deps
from app.api.v1.endpoints import air_conditioners, login, users

api_router = APIRouter()

# Todo el catálogo requiere login; crear/editar/borrar además requieren
# superusuario (ver dependencias en cada endpoint).
api_router.include_router(
    air_conditioners.router,
    prefix="/air-conditioners",
    tags=["Air Conditioners"],
    dependencies=[Depends(deps.get_current_user)],
)

# Público: obtener token
api_router.include_router(login.router, prefix="/login", tags=["Login"])

# POST / es público (registro); el resto exige login (definido por endpoint)
api_router.include_router(users.router, prefix="/users", tags=["Users"])
