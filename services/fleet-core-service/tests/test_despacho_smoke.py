"""
Pruebas de integración del portal de despacho por código QR (RF-18) contra el
stack real. Estos endpoints no usan JWT: la credencial personal del conductor
(cabecera X-Despacho-Token) es lo único que se prueba aquí.

Escriben datos (rotan la credencial de un conductor y crean un viaje que luego
cancelan): correrlas contra una base desechable (FLOTA_BASE_URL).
"""
import os

import pytest
import requests

TOKEN_HEADER = "X-Despacho-Token"
DETALLE_INVALIDO = "Código QR inválido o vencido."


def _rotar(base_url, auth_headers, driver_id) -> dict:
    r = requests.post(f"{base_url}/fleet/drivers/{driver_id}/regenerate-qr", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r


@pytest.fixture(scope="module")
def conductor(base_url, auth_headers):
    """Un conductor activo con vehículo asignado. Su credencial se rota para la prueba
    y, si no tenía una antes, se revoca al terminar."""
    drivers = requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).json()
    elegido = next(d for d in drivers if d["status"] == "activo" and d["assigned_vehicle_id"])
    yield elegido
    if not elegido["has_qr"]:
        requests.post(f"{base_url}/fleet/drivers/{elegido['id']}/revoke-qr", headers=auth_headers)


@pytest.fixture()
def token(base_url, auth_headers, conductor) -> str:
    """Credencial recién emitida para el conductor de prueba."""
    return _rotar(base_url, auth_headers, conductor["id"]).json()["qr_token"]


def _info(base_url, driver_id, token):
    return requests.get(f"{base_url}/fleet/despacho/{driver_id}", headers={TOKEN_HEADER: token})


def test_el_token_solo_se_devuelve_al_emitirlo(base_url, auth_headers, conductor):
    r = _rotar(base_url, auth_headers, conductor["id"])
    body = r.json()
    assert len(body["qr_token"]) == 32
    assert body["has_qr"] is True and body["qr_token_expires_at"]
    assert r.headers["Cache-Control"] == "no-store"

    listado = requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).json()
    detalle = requests.get(f"{base_url}/fleet/drivers/{conductor['id']}", headers=auth_headers).json()
    for d in [*listado, detalle]:
        assert "qr_token" not in d, "el token no debe volver a mostrarse al consultar conductores"
        assert "has_qr" in d
    assert body["qr_token"] not in requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).text


def test_despacho_info_con_credencial_valida(base_url, conductor, token):
    r = _info(base_url, conductor["id"], token)
    assert r.status_code == 200
    body = r.json()
    assert body["driver_name"] == conductor["full_name"]
    assert body["vehicle_id"] == conductor["assigned_vehicle_id"]
    assert r.headers["Cache-Control"] == "no-store"


def test_la_credencial_ya_no_se_acepta_por_la_url(base_url, conductor, token):
    r = requests.get(f"{base_url}/fleet/despacho/{conductor['id']}", params={"token": token})
    assert r.status_code == 401


def test_todos_los_rechazos_responden_igual(base_url, conductor, token):
    """Ausente, falso, de otro conductor o conductor inexistente: mismo 401 y mismo mensaje,
    para que el portal no revele qué falló."""
    inexistente = "00000000-0000-0000-0000-000000000000"
    casos = [
        requests.get(f"{base_url}/fleet/despacho/{conductor['id']}"),
        _info(base_url, conductor["id"], "token-falso-xyz"),
        _info(base_url, conductor["id"], "x" * 500),
        _info(base_url, inexistente, token),
    ]
    assert [r.status_code for r in casos] == [401, 401, 401, 401]
    assert {r.json()["detail"] for r in casos} == {DETALLE_INVALIDO}


def test_rotar_invalida_la_credencial_anterior(base_url, auth_headers, conductor, token):
    nueva = _rotar(base_url, auth_headers, conductor["id"]).json()["qr_token"]
    assert nueva != token
    assert _info(base_url, conductor["id"], token).status_code == 401
    assert _info(base_url, conductor["id"], nueva).status_code == 200


def test_revocar_deja_al_conductor_sin_credencial(base_url, auth_headers, conductor, token):
    assert _info(base_url, conductor["id"], token).status_code == 200
    r = requests.post(f"{base_url}/fleet/drivers/{conductor['id']}/revoke-qr", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["has_qr"] is False and body["qr_token_expires_at"] is None and body["qr_token_last_used_at"] is None
    assert _info(base_url, conductor["id"], token).status_code == 401


def test_despacho_registra_viaje_en_curso_sin_login(base_url, auth_headers, conductor, token):
    """El conductor nunca pasa por /auth/login: la credencial del QR reemplaza esa
    autenticación por completo para este flujo."""
    info = _info(base_url, conductor["id"], token).json()

    r = requests.post(
        f"{base_url}/fleet/despacho/{conductor['id']}",
        headers={TOKEN_HEADER: token},
        json={
            "origin": "Puerto de Machala",
            "destination": "Ibarra",
            "start_mileage_km": info["vehicle_current_mileage_km"],
            "remission_guide": "GR-TEST-0001",
            "cargo_type": "Carga de prueba",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["trip"]["status"] == "en_curso"
    assert "Buen viaje" in body["message"]

    # Se ve igual que cualquier otro viaje desde el panel de administración
    # (created_by=None es la única diferencia: lo registró el conductor).
    admin_view = requests.get(f"{base_url}/fleet/trips/{body['trip']['id']}", headers=auth_headers)
    assert admin_view.status_code == 200
    assert admin_view.json()["created_by"] is None
    assert admin_view.json()["remission_guide"] == "GR-TEST-0001"
    requests.patch(f"{base_url}/fleet/trips/{body['trip']['id']}/cancel", headers=auth_headers)

    # Cada uso exitoso deja constancia del último uso de la credencial.
    detalle = requests.get(f"{base_url}/fleet/drivers/{conductor['id']}", headers=auth_headers).json()
    assert detalle["qr_token_last_used_at"] is not None


def test_registrar_viaje_sin_credencial_se_rechaza(base_url, conductor):
    r = requests.post(
        f"{base_url}/fleet/despacho/{conductor['id']}",
        json={"origin": "A", "destination": "B", "start_mileage_km": 0},
    )
    assert r.status_code == 401


@pytest.mark.skipif(
    not os.getenv("RUN_RATE_LIMIT_TESTS"),
    reason="agota el cupo del gateway durante ~1 min y afectaría a otras corridas; activar con RUN_RATE_LIMIT_TESTS=1",
)
def test_el_gateway_limita_los_intentos_de_adivinar_la_credencial(base_url, conductor):
    codigos = [_info(base_url, conductor["id"], f"intento-{i}").status_code for i in range(60)]
    assert 401 in codigos
    assert 429 in codigos, "tras la ráfaga permitida el gateway debe responder 429"
    assert codigos.index(429) > 5, "las primeras peticiones legítimas no deben bloquearse"
