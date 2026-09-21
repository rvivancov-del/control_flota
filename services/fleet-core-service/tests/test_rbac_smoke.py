"""
Pruebas de integración de los permisos por rol (RF-03) contra el stack real, con una
sesión de operador de verdad (JWT emitido por auth-service). La matriz completa
endpoint por endpoint está en test_roles.py; aquí se comprueba de punta a punta que
el operador hace su trabajo diario y que lo administrativo se rechaza sin efectos.
"""
import uuid
from datetime import datetime, timedelta, timezone

import requests

VEHICULO_NUEVO = {"plate": "ZZZ-0001", "brand": "Prueba", "model": "RBAC", "year": 2024, "current_mileage_km": 0, "status": "activo"}
CONDUCTOR_NUEVO = {"full_name": "Prueba RBAC", "license_number": "RBAC-0001"}


def _conteos(base_url, headers):
    vehiculos = requests.get(f"{base_url}/fleet/vehicles", headers=headers).json()
    conductores = requests.get(f"{base_url}/fleet/drivers", headers=headers).json()
    return len(vehiculos), len(conductores)


def test_el_operador_consulta_catalogo_y_no_ve_tokens(base_url, operator_headers):
    vehiculos = requests.get(f"{base_url}/fleet/vehicles", headers=operator_headers)
    conductores = requests.get(f"{base_url}/fleet/drivers", headers=operator_headers)
    assert vehiculos.status_code == 200 and len(vehiculos.json()) > 0
    assert conductores.status_code == 200 and len(conductores.json()) > 0
    assert all("qr_token" not in d for d in conductores.json()), "el operador no debe ver el token del QR"


def test_el_operador_no_puede_administrar_el_catalogo_ni_el_qr(base_url, auth_headers, operator_headers):
    antes = _conteos(base_url, auth_headers)
    vehiculo = requests.get(f"{base_url}/fleet/vehicles", headers=auth_headers).json()[0]
    conductor = requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).json()[0]

    intentos = [
        requests.post(f"{base_url}/fleet/vehicles", headers=operator_headers, json=VEHICULO_NUEVO),
        requests.patch(f"{base_url}/fleet/vehicles/{vehiculo['id']}", headers=operator_headers, json={"status": "inactivo"}),
        requests.post(f"{base_url}/fleet/drivers", headers=operator_headers, json=CONDUCTOR_NUEVO),
        requests.patch(f"{base_url}/fleet/drivers/{conductor['id']}", headers=operator_headers, json={"status": "inactivo"}),
        requests.post(f"{base_url}/fleet/drivers/{conductor['id']}/regenerate-qr", headers=operator_headers),
        requests.post(f"{base_url}/fleet/drivers/{conductor['id']}/revoke-qr", headers=operator_headers),
    ]
    assert [r.status_code for r in intentos] == [403] * 6

    # Ningún intento tuvo efecto: mismos conteos y mismo estado.
    assert _conteos(base_url, auth_headers) == antes
    assert requests.get(f"{base_url}/fleet/vehicles/{vehiculo['id']}", headers=auth_headers).json()["status"] == vehiculo["status"]
    assert requests.get(f"{base_url}/fleet/drivers/{conductor['id']}", headers=auth_headers).json()["status"] == conductor["status"]


def test_el_operador_opera_viajes_gastos_y_mantenimiento(base_url, auth_headers, operator_headers):
    vehiculo = next(v for v in requests.get(f"{base_url}/fleet/vehicles", headers=auth_headers).json() if v["status"] == "activo")
    conductor = next(d for d in requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).json() if d["status"] == "activo")
    salida = datetime.now(timezone.utc) + timedelta(hours=1)

    viaje = requests.post(
        f"{base_url}/fleet/trips",
        headers=operator_headers,
        json={
            "vehicle_id": vehiculo["id"],
            "driver_id": conductor["id"],
            "origin": "Guayaquil",
            "destination": "Quito",
            "departure_at": salida.isoformat(),
            "start_mileage_km": vehiculo["current_mileage_km"],
        },
    )
    assert viaje.status_code == 201, viaje.text
    trip_id = viaje.json()["id"]

    gasto = requests.post(
        f"{base_url}/fleet/trips/{trip_id}/expenses",
        headers=operator_headers,
        json={"type": "peaje", "amount": "3.50", "expense_date": salida.date().isoformat()},
    )
    assert gasto.status_code == 201, gasto.text

    assert requests.get(f"{base_url}/fleet/trips/{trip_id}/expenses", headers=operator_headers).status_code == 200
    assert requests.get(f"{base_url}/fleet/maintenance/alerts", headers=operator_headers).status_code == 200
    assert requests.get(f"{base_url}/fleet/maintenance/policy", headers=operator_headers).status_code == 200

    mantenimiento = requests.post(
        f"{base_url}/fleet/vehicles/{vehiculo['id']}/maintenance",
        headers=operator_headers,
        json={
            "maintenance_type": "aceite",
            "category": "preventivo",
            "scheduled_mileage_km": vehiculo["current_mileage_km"] + 20000,
        },
    )
    assert mantenimiento.status_code == 201, mantenimiento.text
    completado = requests.patch(
        f"{base_url}/fleet/maintenance/{mantenimiento.json()['id']}/complete",
        headers=operator_headers,
        json={"performed_mileage_km": vehiculo["current_mileage_km"], "performed_at": salida.date().isoformat(), "cost": "55.00"},
    )
    assert completado.status_code == 200 and completado.json()["status"] == "completado"

    cancelado = requests.patch(f"{base_url}/fleet/trips/{trip_id}/cancel", headers=operator_headers)
    assert cancelado.status_code == 200 and cancelado.json()["status"] == "anulado"


def test_un_token_de_rol_desconocido_no_accede(base_url):
    """JWT bien firmado (mismo secreto de desarrollo) pero con un rol que no existe."""
    from jose import jwt

    payload = {"sub": str(uuid.uuid4()), "role": "auditor", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    token = jwt.encode(payload, "changeme_local_only", algorithm="HS256")
    r = requests.get(f"{base_url}/fleet/vehicles", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
