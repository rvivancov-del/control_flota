"""Pruebas de la matriz de permisos por rol (RF-03) de fleet-core-service.

No requieren el stack ni la base de datos: se sustituye la sesión por un objeto
que falla al usarse. Como las dependencias de autorización se resuelven antes
que la lógica del endpoint, un 401/403 prueba que el rol fue rechazado, y
cualquier otro código (422, 500 por la base ausente) prueba que la autorización
pasó y la petición llegó al endpoint.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jose import jwt

from app.core import security
from app.core.database import get_db
from app.main import app

ID = "11111111-1111-1111-1111-111111111111"
RECHAZADO = (401, 403)

# Endpoints exentos de la matriz: salud y portal de despacho, que se autentica con la
# credencial del QR (ver test_qr_token.py y tests/test_despacho_smoke.py).
EXENTOS = {("GET", "/health")}
EXENTOS_PREFIJO = ("/despacho/",)

# (método, ruta) -> roles autorizados
ADMIN = {"admin"}
AMBOS = {"admin", "operador"}
MATRIZ = {
    # Catálogo: consulta para ambos, alta y edición solo admin
    ("GET", "/vehicles"): AMBOS,
    ("GET", "/vehicles/{vehicle_id}"): AMBOS,
    ("POST", "/vehicles"): ADMIN,
    ("PATCH", "/vehicles/{vehicle_id}"): ADMIN,
    ("GET", "/drivers"): AMBOS,
    ("GET", "/drivers/license-types"): AMBOS,
    ("GET", "/drivers/{driver_id}"): AMBOS,
    ("POST", "/drivers"): ADMIN,
    ("PATCH", "/drivers/{driver_id}"): ADMIN,
    ("POST", "/drivers/{driver_id}/regenerate-qr"): ADMIN,
    ("POST", "/drivers/{driver_id}/revoke-qr"): ADMIN,
    ("POST", "/drivers/{driver_id}/anonymize"): ADMIN,
    # Operación del día a día: ambos
    ("POST", "/trips"): AMBOS,
    ("GET", "/trips"): AMBOS,
    ("GET", "/trips/{trip_id}"): AMBOS,
    ("PATCH", "/trips/{trip_id}/start"): AMBOS,
    ("PATCH", "/trips/{trip_id}/cancel"): AMBOS,
    ("PATCH", "/trips/{trip_id}/revenue"): AMBOS,
    ("PATCH", "/trips/{trip_id}/close"): AMBOS,
    ("POST", "/trips/{trip_id}/expenses"): AMBOS,
    ("GET", "/trips/{trip_id}/expenses"): AMBOS,
    ("PATCH", "/trips/{trip_id}/expenses/{expense_id}"): AMBOS,
    ("POST", "/vehicles/{vehicle_id}/maintenance"): AMBOS,
    ("GET", "/vehicles/{vehicle_id}/maintenance"): AMBOS,
    ("PATCH", "/maintenance/{maintenance_id}/complete"): AMBOS,
    ("PATCH", "/maintenance/{maintenance_id}/cost"): AMBOS,
    ("GET", "/expenses"): AMBOS,
    ("GET", "/maintenance"): AMBOS,
    ("GET", "/maintenance/alerts"): AMBOS,
    ("GET", "/maintenance/policy"): AMBOS,
    ("GET", "/analytics/expenses"): AMBOS,
    ("GET", "/analytics/trips"): AMBOS,
    ("GET", "/analytics/routes"): AMBOS,
    ("GET", "/analytics/maintenance"): AMBOS,
    # Costos fijos y de personal: información financiera, solo admin
    ("GET", "/analytics/fixed-costs"): ADMIN,
    ("GET", "/analytics/personnel-costs"): ADMIN,
    ("GET", "/fixed-costs"): ADMIN,
    ("POST", "/fixed-costs"): ADMIN,
    ("PATCH", "/fixed-costs/{cost_id}"): ADMIN,
    ("DELETE", "/fixed-costs/{cost_id}"): ADMIN,
    ("GET", "/personnel-costs"): ADMIN,
    ("POST", "/personnel-costs"): ADMIN,
    ("PATCH", "/personnel-costs/{cost_id}"): ADMIN,
    ("DELETE", "/personnel-costs/{cost_id}"): ADMIN,
}


class _SinBaseDeDatos:
    """Sesión de mentira: cualquier uso falla, así el endpoint responde 500."""

    def __getattr__(self, name):
        raise RuntimeError("sin base de datos en las pruebas unitarias")


def _sin_base_de_datos():
    yield _SinBaseDeDatos()


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_db] = _sin_base_de_datos
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db, None)


def _token(role: str, **extra) -> dict:
    payload = {"sub": str(uuid.uuid4()), "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **extra}
    jwt_token = jwt.encode(payload, security.JWT_SECRET_KEY, algorithm=security.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {jwt_token}"}


def _url(template: str) -> str:
    out = template
    for name in ("vehicle_id", "driver_id", "trip_id", "expense_id", "maintenance_id", "cost_id"):
        out = out.replace("{" + name + "}", ID)
    assert "{" not in out, out
    return out


def _rutas_de_la_aplicacion() -> set[tuple[str, str]]:
    rutas = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                rutas.add((method, route.path))
    return {(m, p) for m, p in rutas if (m, p) not in EXENTOS and not p.startswith(EXENTOS_PREFIJO)}


def _llamar(client: TestClient, method: str, path: str, headers=None):
    return client.request(method, _url(path), headers=headers or {}, json={})


def test_la_matriz_cubre_todos_los_endpoints_de_la_aplicacion():
    """Si alguien agrega un endpoint sin decidir su permiso, esta prueba falla."""
    assert _rutas_de_la_aplicacion() == set(MATRIZ)


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
def test_sin_token_se_rechaza(client, method, path):
    assert _llamar(client, method, path).status_code in RECHAZADO


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
def test_un_token_invalido_se_rechaza(client, method, path):
    r = _llamar(client, method, path, {"Authorization": "Bearer no-es-un-jwt"})
    assert r.status_code == 401


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
def test_un_token_firmado_con_otra_clave_se_rechaza(client, method, path):
    falso = jwt.encode(
        {"sub": ID, "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "otra-clave", algorithm=security.JWT_ALGORITHM,
    )
    assert _llamar(client, method, path, {"Authorization": f"Bearer {falso}"}).status_code == 401


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
def test_un_rol_desconocido_no_accede_a_nada(client, method, path):
    assert _llamar(client, method, path, _token("auditor")).status_code == 403


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
@pytest.mark.parametrize("role", ["admin", "operador"])
def test_cada_rol_recibe_lo_que_la_matriz_dice(client, method, path, role):
    status = _llamar(client, method, path, _token(role)).status_code
    if role in MATRIZ[(method, path)]:
        assert status not in RECHAZADO, f"{role} debería poder {method} {path}, recibió {status}"
    else:
        assert status == 403, f"{role} no debería poder {method} {path}, recibió {status}"


def test_el_operador_no_puede_administrar_catalogo_ni_qr():
    """Resumen legible de RF-03: lo que el operador NO puede hacer."""
    prohibidas = sorted(k for k, roles in MATRIZ.items() if "operador" not in roles)
    assert prohibidas == [
        ("DELETE", "/fixed-costs/{cost_id}"),
        ("DELETE", "/personnel-costs/{cost_id}"),
        ("GET", "/analytics/fixed-costs"),
        ("GET", "/analytics/personnel-costs"),
        ("GET", "/fixed-costs"),
        ("GET", "/personnel-costs"),
        ("PATCH", "/drivers/{driver_id}"),
        ("PATCH", "/fixed-costs/{cost_id}"),
        ("PATCH", "/personnel-costs/{cost_id}"),
        ("PATCH", "/vehicles/{vehicle_id}"),
        ("POST", "/drivers"),
        ("POST", "/drivers/{driver_id}/anonymize"),
        ("POST", "/drivers/{driver_id}/regenerate-qr"),
        ("POST", "/drivers/{driver_id}/revoke-qr"),
        ("POST", "/fixed-costs"),
        ("POST", "/personnel-costs"),
        ("POST", "/vehicles"),
    ]


@pytest.mark.parametrize("method,path", sorted(MATRIZ))
@pytest.mark.parametrize("role", ["admin", "operador"])
def test_un_token_con_cambio_de_clave_pendiente_no_opera(client, method, path, role):
    """RNF-02: auth-service marca con `mcp` el token de quien debe cambiar su contraseña."""
    r = _llamar(client, method, path, _token(role, mcp=True))
    assert r.status_code == 403 and "cambiar su contraseña" in r.text
