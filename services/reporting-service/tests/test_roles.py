"""Pruebas de la matriz de permisos por rol (RF-03) de reporting-service.

No requieren el stack: se sustituye el cliente de fleet-core-service por uno que
falla al usarse (503). Como la autorización se resuelve antes que la lógica del
endpoint, 401/403 prueba que el rol fue rechazado y cualquier otro código prueba
que la petición llegó al endpoint.
"""
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jose import jwt

from app.core import security
from app.dashboards import router as dashboards_router
from app.main import app

RECHAZADO = (401, 403)
EXENTOS = {("GET", "/health")}

ADMIN = {"admin"}
AMBOS = {"admin", "operador"}
MATRIZ = {
    # Tablero y reportes en pantalla: ambos roles
    ("GET", "/dashboard/summary"): AMBOS,
    ("GET", "/dashboard/trend"): AMBOS,
    ("GET", "/dashboard/records"): AMBOS,
    ("GET", "/dashboard/drivers"): AMBOS,
    ("GET", "/dashboard/routes"): AMBOS,
    ("GET", "/dashboard/maintenance-status"): AMBOS,
    ("GET", "/dashboard/maintenance-priority"): AMBOS,
    ("GET", "/dashboard/vehicle-attention"): AMBOS,
    ("GET", "/reports/maintenance"): AMBOS,
    # Exportación de reportes: solo admin
    ("GET", "/reports/costs.xlsx"): ADMIN,
    ("GET", "/reports/costs.pdf"): ADMIN,
}


class _FleetSinRed:
    """Cliente de fleet-core de mentira: toda llamada falla como si no hubiera red."""

    def __getattr__(self, name):
        def _falla(*args, **kwargs):
            raise httpx.ConnectError("sin red en las pruebas unitarias")

        return _falla


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[dashboards_router._fleet_client] = lambda: _FleetSinRed()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(dashboards_router._fleet_client, None)


def _token(role: str, **extra) -> dict:
    payload = {"sub": str(uuid.uuid4()), "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **extra}
    return {"Authorization": "Bearer " + jwt.encode(payload, security.JWT_SECRET_KEY, algorithm=security.JWT_ALGORITHM)}


def _rutas_de_la_aplicacion() -> set[tuple[str, str]]:
    rutas = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                rutas.add((method, route.path))
    return rutas - EXENTOS


def test_la_matriz_cubre_todos_los_endpoints_de_la_aplicacion():
    """Si alguien agrega un endpoint sin decidir su permiso, esta prueba falla."""
    assert _rutas_de_la_aplicacion() == set(MATRIZ)


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
def test_sin_token_se_rechaza(client, method, path):
    assert client.request(method, path).status_code in RECHAZADO


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
def test_un_token_invalido_se_rechaza(client, method, path):
    assert client.request(method, path, headers={"Authorization": "Bearer no-es-un-jwt"}).status_code == 401


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
def test_un_rol_desconocido_no_accede_a_nada(client, method, path):
    assert client.request(method, path, headers=_token("auditor")).status_code == 403


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
@pytest.mark.parametrize("role", ["admin", "operador"])
def test_cada_rol_recibe_lo_que_la_matriz_dice(client, method, path, role):
    status = client.request(method, path, headers=_token(role)).status_code
    if role in MATRIZ[(method, path)]:
        assert status not in RECHAZADO, f"{role} debería poder {method} {path}, recibió {status}"
    else:
        assert status == 403, f"{role} no debería poder {method} {path}, recibió {status}"


def test_solo_admin_exporta_reportes():
    exclusivos = sorted(k for k, roles in MATRIZ.items() if roles == ADMIN)
    assert exclusivos == [("GET", "/reports/costs.pdf"), ("GET", "/reports/costs.xlsx")]


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
@pytest.mark.parametrize("role", ["admin", "operador"])
def test_un_token_con_cambio_de_clave_pendiente_no_opera(client, method, path, role):
    """RNF-02: auth-service marca con `mcp` el token de quien debe cambiar su contraseña."""
    r = client.request(method, path, headers=_token(role, mcp=True))
    assert r.status_code == 403 and "cambiar su contraseña" in r.text
