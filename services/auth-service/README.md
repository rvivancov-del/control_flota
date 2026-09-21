# auth-service

Responsable de: autenticación, usuarios y roles (RF-01 a RF-03 del Avance 1).

## Estructura

```
app/
├── main.py         # instancia FastAPI + routers + /health
├── seed.py         # siembra idempotente: roles admin/operador + usuario admin inicial
├── core/
│   ├── database.py  # engine, sesión, esquema "auth"
│   ├── security.py  # hash de contraseñas (bcrypt) y JWT
│   ├── deps.py       # get_current_user, require_role(...)
│   ├── lockout.py     # RNF-03: bloqueo temporal por intentos fallidos
│   └── config_guard.py # RNF-02: no arranca con secretos por defecto fuera de desarrollo
├── models/          # Role, User (SQLAlchemy)
├── schemas/         # RoleRead, UserCreate/Update/Read, LoginRequest, Token (Pydantic)
└── routers/
    ├── auth.py       # POST /auth/login · GET /auth/me · POST /auth/change-password
    ├── users.py       # POST/GET/PATCH /users (solo rol admin)
    └── roles.py        # GET /roles (solo rol admin)
```

## Endpoints

| Método | Ruta | Rol | RF |
|---|---|---|---|
| POST | `/auth/login` | público | RF-02 |
| GET | `/auth/me` | cualquier usuario autenticado (también con cambio de contraseña pendiente) | RF-02 |
| POST | `/auth/change-password` | cualquier usuario autenticado (también con cambio pendiente) | RNF-02 |
| POST | `/users` | admin | RF-01 |
| GET | `/users`, `/users/{id}` | admin | RF-01 |
| PATCH | `/users/{id}` | admin (edición, incluida desactivación) | RF-01 |
| POST | `/users/{id}/unlock` | admin | RNF-03 |
| GET | `/roles` | admin | RF-03 |

## Seguridad de cuentas (RNF-02, RNF-03)

- **Bloqueo temporal (RNF-03):** tras `LOGIN_MAX_FAILED_ATTEMPTS` (5) contraseñas incorrectas seguidas la cuenta se
  bloquea `LOGIN_LOCKOUT_MINUTES` (15) minutos (`users.locked_until`); durante el bloqueo ni la contraseña
  correcta entra. Se desbloquea sola al vencer, o antes con `POST /users/{id}/unlock`. El bloqueo no es lo
  mismo que desactivar la cuenta (`is_active`), que solo hace un administrador. Todos los rechazos de `/login`
  (usuario inexistente, contraseña errónea, cuenta inactiva o bloqueada) responden igual, y el gateway limita
  el login a 10 peticiones por minuto.
- **Nunca sin administrador (RNF-03):** no se puede desactivar ni degradar al único administrador activo (409).
- **Cambio obligatorio de contraseña (RNF-02):** con `must_change_password` el usuario solo puede usar `/auth/me`
  y `/auth/change-password`; su JWT lleva `mcp: true` y fleet-core y reporting lo rechazan (403) hasta que cambie
  la contraseña y reciba un token nuevo. Se activa para el administrador sembrado en producción, para las cuentas
  que el administrador cree con la casilla correspondiente y cuando otro administrador fija su contraseña.
  `POST /auth/change-password` exige la contraseña actual (equivocarse cuenta como intento fallido), una nueva
  distinta y con letras y números.
- **Sin secretos por defecto fuera de desarrollo (RNF-02):** `APP_ENV=development` solo en un equipo local (los
  `.env.example` la traen). Si `APP_ENV` falta o vale otra cosa, el servicio no arranca con la clave JWT (o una de
  menos de 32 caracteres) ni la contraseña de la base de datos por defecto, y el sembrado no crea al administrador con la
  clave publicada (`Admin1234`). fleet-core y reporting aplican la misma guardia.

Credenciales iniciales (entorno local, ver `.env.example`): usuario `admin`,
contraseña `Admin1234` — creadas automáticamente por `app/seed.py` en el
primer arranque. En desarrollo no se pide cambiarla (comodidad para la demo);
en producción es obligatoria una clave inicial propia y se pide cambiarla al primer ingreso.

## Cómo lo consumen los otros servicios

`fleet-core-service` y `reporting-service` no llaman a este servicio por
HTTP para verificar sesiones: decodifican el JWT ellos mismos con la misma
clave simétrica (`JWT_SECRET_KEY`, HS256), sin ir a la base de datos. Este
es el único servicio que conoce la tabla `users` y emite tokens.

## Pruebas

```bash
docker compose exec auth-service sh -c "pip install -q -r requirements-test.txt && pytest -q"
```

Cobertura real medida con `coverage.py`: 71%.
