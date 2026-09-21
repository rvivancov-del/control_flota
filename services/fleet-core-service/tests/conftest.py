import os

import pytest
import requests

# Las pruebas de integración escriben datos (viajes, conductores de prueba...): apuntar a una
# base desechable con FLOTA_BASE_URL (p. ej. http://localhost:18080/api, ver scripts/README.md).
BASE = os.getenv("FLOTA_BASE_URL", "http://localhost:8080/api")

OPERADOR_PRUEBA = ("smoke_operador", "Operador1234")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE


@pytest.fixture(scope="session")
def admin_token(base_url: str) -> str:
    r = requests.post(f"{base_url}/auth/login", json={"username": "admin", "password": "Admin1234"})
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def operator_headers(base_url: str, auth_headers: dict):
    """Sesión de un usuario con rol operador (RF-03). La cuenta de prueba se crea la
    primera vez, se reactiva en cada corrida y se desactiva al terminar."""
    username, password = OPERADOR_PRUEBA
    roles = requests.get(f"{base_url}/auth/roles", headers=auth_headers).json()
    role_id = next(r["id"] for r in roles if r["name"] == "operador")
    users = requests.get(f"{base_url}/auth/users", headers=auth_headers).json()
    existing = next((u for u in users if u["username"] == username), None)
    if existing is None:
        created = requests.post(
            f"{base_url}/auth/users",
            headers=auth_headers,
            json={"username": username, "password": password, "full_name": "Operador de prueba", "role_id": role_id},
        )
        created.raise_for_status()
        user_id = created.json()["id"]
    else:
        user_id = existing["id"]
        requests.patch(
            f"{base_url}/auth/users/{user_id}",
            headers=auth_headers,
            json={"is_active": True, "password": password, "role_id": role_id},
        ).raise_for_status()
    login = requests.post(f"{base_url}/auth/login", json={"username": username, "password": password})
    login.raise_for_status()
    yield {"Authorization": f"Bearer {login.json()['access_token']}"}
    requests.patch(f"{base_url}/auth/users/{user_id}", headers=auth_headers, json={"is_active": False})
