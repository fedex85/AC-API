# Importar todos los modelos aquí para que Alembic los detecte
from app.db.session import Base  # noqa: F401
from app.models.air_conditioner import AirConditioner  # noqa: F401
from app.models.user import User  # noqa: F401
