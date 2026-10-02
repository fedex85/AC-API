from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env en la raíz del proyecto, independientemente del directorio de ejecución
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    SQL_ECHO: bool = False  # True solo para depurar consultas SQL

    # Seguridad
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Protección del login (intentos fallidos por IP+email dentro de la ventana)
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 300

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Air Conditioning API"
    VERSION: str = "1.0.0"

    # CORS: lista de orígenes permitidos (en producción, especificarlos)
    CORS_ORIGINS: list[str] = ["*"]

    # Server
    HOST: str = "127.0.0.1"  # 0.0.0.0 solo si quieres exponerla en la red
    PORT: int = 8000
    RELOAD: bool = False  # True solo en desarrollo

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
