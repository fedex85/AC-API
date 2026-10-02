from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.core.rate_limit import FailedAttemptLimiter, raise_too_many_attempts
from app.core.security import create_access_token
from app.crud import user as crud_user

router = APIRouter()

# Límite de intentos fallidos de login (ver app/core/rate_limit.py)
login_limiter = FailedAttemptLimiter(window_seconds=settings.LOGIN_WINDOW_SECONDS)


@router.post("/access-token")
def login_access_token(
    request: Request,
    db: Annotated[Session, Depends(deps.get_db)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """
    Endpoint de login para obtener un token JWT.
    Tras varios intentos fallidos desde la misma IP responde 429.
    """
    ip = request.client.host if request.client else "unknown"
    key_pair = f"{ip}|{form_data.username.strip().lower()}"
    key_ip = f"{ip}|*"

    # Por IP+email: LOGIN_MAX_ATTEMPTS; por IP (probando muchos emails): 4 veces más
    wait = max(
        login_limiter.retry_after(key_pair, settings.LOGIN_MAX_ATTEMPTS),
        login_limiter.retry_after(key_ip, settings.LOGIN_MAX_ATTEMPTS * 4),
    )
    if wait:
        raise_too_many_attempts(wait)

    # OAuth2 usa el campo 'username', pero aquí es el email
    user = crud_user.authenticate(
        db, email=form_data.username, password=form_data.password
    )

    if not user:
        login_limiter.record_failure(key_pair)
        login_limiter.record_failure(key_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not crud_user.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario inactivo"
        )

    login_limiter.reset(key_pair)

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}
