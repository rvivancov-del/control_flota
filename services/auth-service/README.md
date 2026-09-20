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
│   └── deps.py       # get_current_user, require_role(...)
├── models/          # Role, User (SQLAlchemy)
├── schemas/         # RoleRead, UserCreate/Update/Read, LoginRequest, Token (Pydantic)
└── routers/
    ├── auth.py       # POST /auth/login · GET /auth/me
    ├── users.py       # POST/GET/PATCH /users (solo rol admin)
    └── roles.py        # GET /roles (solo rol admin)
```

## Endpoints

| Método | Ruta | Rol | RF |
|---|---|---|---|
| POST | `/auth/login` | público | RF-02 |
| GET | `/auth/me` | cualquier usuario autenticado | RF-02 |
| POST | `/users` | admin | RF-01 |
| GET | `/users`, `/users/{id}` | admin | RF-01 |
| PATCH | `/users/{id}` | admin (edición, incluida desactivación) | RF-01 |
| GET | `/roles` | admin | RF-03 |

Credenciales iniciales (entorno local, ver `.env.example`): usuario `admin`,
contraseña `Admin1234` — creadas automáticamente por `app/seed.py` en el
primer arranque. Cámbialas antes de cualquier despliegue real.

RNF-03 implementado: 5 intentos fallidos consecutivos desactivan la cuenta
(`is_active = false`); reactivarla desde `PATCH /users/{id}` limpia el
contador.

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
