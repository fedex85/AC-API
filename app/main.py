from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.api import api_router
from app.core.config import settings

# Las tablas se crean/actualizan exclusivamente con Alembic:
#   alembic upgrade head

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API REST para gestión de aires acondicionados",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# CORS: la autenticación va por header Authorization (Bearer), no por cookies,
# así que no se necesitan credenciales (y "*" + credenciales no es válido).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Panel web (HTML/CSS/JS estático, sin dependencias) en /panel/
PANEL_DIR = Path(__file__).resolve().parent / "static" / "panel"

PANEL_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)


@app.middleware("http")
async def panel_security_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/panel"):
        response.headers["Content-Security-Policy"] = PANEL_CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/panel", StaticFiles(directory=PANEL_DIR, html=True), name="panel")


@app.get("/")
def root():
    return {
        "message": "Air Conditioning API",
        "version": settings.VERSION,
        "docs": "/docs",
        "panel": "/panel/",
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Comprueba que la API responde y que la base de datos es accesible."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "error"},
        )
    return {"status": "healthy", "database": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
    )
