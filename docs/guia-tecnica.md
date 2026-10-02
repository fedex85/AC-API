# Guía técnica

[← Volver al README](../README.md)

API REST (FastAPI + SQLAlchemy + PostgreSQL) para gestionar un catálogo de aires
acondicionados, con autenticación JWT y permisos por rol.

## Requisitos

- Python 3.12 o superior
- PostgreSQL con una base de datos creada (por defecto `ac_api_db`)

## Instalación

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuración

Copia `.env.example` a `.env` y rellena los valores (no subas `.env` a git):

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | `postgresql://usuario:contraseña@localhost:5432/ac_api_db` |
| `SECRET_KEY` | Clave para firmar los tokens. Genera una con `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token (por defecto 30) |
| `CORS_ORIGINS` | Lista JSON de orígenes permitidos. En producción, pon los reales |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | Intentos fallidos de login permitidos y ventana (5 / 300 s) |
| `SQL_ECHO`, `RELOAD` | `True` solo para depurar |

## Puesta en marcha

```powershell
alembic upgrade head          # crea las tablas
python create_superuser.py    # crea el primer administrador
python -m uvicorn app.main:app --reload
```

- Panel web: <http://localhost:8000/panel/>
- Documentación interactiva de la API: <http://localhost:8000/docs>

## Panel web

`/panel/` es una interfaz visual servida por la propia API (HTML, CSS y JavaScript
sin dependencias; no necesita Node ni compilar nada):

- Inicio de sesión y creación de cuenta.
- Catálogo con filtros (marca, tipo, eficiencia, BTU, precio, disponibilidad,
  características), orden y paginación. La escala de eficiencia A+++ a D es a la vez
  filtro y distintivo de cada equipo.
- Los administradores pueden añadir, editar y eliminar equipos. El resto de
  usuarios solo consulta.
- Funciona en escritorio y móvil, y sigue el modo claro u oscuro del sistema.
- La moneda se cambia en una constante (`CURRENCY`) al principio de
  `app/static/panel/panel.js`.
- El token de sesión se guarda en `sessionStorage` (se borra al cerrar la pestaña) y
  la página se sirve con una política de seguridad de contenido (CSP) estricta.

## Autenticación y permisos

- `POST /api/v1/users/` — registro público (siempre crea un usuario normal).
- `POST /api/v1/login/access-token` — login (`username` = email). Devuelve un JWT.
  Tras varios intentos fallidos desde la misma IP responde `429`.
- Todos los endpoints de `/api/v1/air-conditioners` exigen login.
  Crear, modificar y borrar exigen además ser **superusuario**.
- En `/docs`, el botón **Authorize** permite iniciar sesión y probar los endpoints.

## Endpoints de aires acondicionados

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/api/v1/air-conditioners/` | usuario autenticado |
| GET | `/api/v1/air-conditioners/{id}` | usuario autenticado |
| POST | `/api/v1/air-conditioners/` | superusuario |
| PATCH | `/api/v1/air-conditioners/{id}` | superusuario (actualización parcial) |
| DELETE | `/api/v1/air-conditioners/{id}` | superusuario |

Filtros del listado (todos opcionales y combinables): `brand`, `ac_type`,
`energy_rating`, `min_btu`, `max_btu`, `min_price`, `max_price`, `available`,
`has_inverter`, `has_heating`, `has_wifi`. Orden: `sort_by`
(`id`, `brand`, `price`, `btu_capacity`, `power_consumption`, `created_at`) y
`order` (`asc`/`desc`). Paginación: `skip` y `limit` (máx. 100). La respuesta
incluye `total` (resultados que cumplen los filtros, sin paginar).

Ejemplo: `GET /api/v1/air-conditioners/?ac_type=split&min_btu=9000&sort_by=price&order=asc`

## Health check

`GET /health` devuelve `200` si la API y la base de datos responden, y `503` si
la base de datos no es accesible.

## Tests

Los tests usan SQLite en memoria; no tocan tu base PostgreSQL.

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Migraciones

```powershell
alembic revision --autogenerate -m "descripcion del cambio"
alembic upgrade head
```

## Notas de despliegue

- El limitador de login vive en memoria de un solo proceso. Con varios workers o
  réplicas conviene un almacén compartido (p. ej. Redis).
- Detrás de un proxy inverso, la IP que ve la API es la del proxy; configura
  uvicorn con `--proxy-headers` y `--forwarded-allow-ips` para que el límite
  se aplique por IP real.
- Usa una `SECRET_KEY` larga y aleatoria y orígenes CORS concretos.
