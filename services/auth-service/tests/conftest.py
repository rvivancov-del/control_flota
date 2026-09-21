import os

import pytest
import requests

# Ver scripts/README.md: apuntar a una base desechable con FLOTA_BASE_URL.
BASE = os.getenv("FLOTA_BASE_URL", "http://localhost:8080/api")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE


@pytest.fixture(scope="session")
def admin_token(base_url: str) -> str:
    r = requests.post(f"{base_url}/auth/login", json={"username": "admin", "password": "Admin1234"})
    r.raise_for_status()
    return r.json()["access_token"]
