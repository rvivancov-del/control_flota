"""
Pruebas de integración del portal de despacho por código QR (RF-18).
A diferencia del resto de fleet-core-service, estos endpoints no usan JWT
— el "token" del conductor es lo único que se prueba aquí.
"""
import requests


def _driver_con_qr(base_url, auth_headers):
    """Toma cualquier conductor activo, con vehículo asignado y con
    qr_token — el backfill de esta sesión ya se lo dio a los 12 sembrados."""
    drivers = requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).json()
    for d in drivers:
        if d.get("qr_token") and d.get("assigned_vehicle_id"):
            return d
    raise AssertionError("Ningún conductor de prueba tiene qr_token + vehículo asignado.")


def test_despacho_info_con_token_valido(base_url, auth_headers):
    driver = _driver_con_qr(base_url, auth_headers)
    r = requests.get(f"{base_url}/fleet/despacho/{driver['id']}", params={"token": driver["qr_token"]})
    assert r.status_code == 200
    body = r.json()
    assert body["driver_name"] == driver["full_name"]
    assert body["vehicle_id"] == driver["assigned_vehicle_id"]


def test_despacho_info_con_token_invalido_rechaza(base_url, auth_headers):
    driver = _driver_con_qr(base_url, auth_headers)
    r = requests.get(f"{base_url}/fleet/despacho/{driver['id']}", params={"token": "token-falso-xyz"})
    assert r.status_code == 401


def test_despacho_registra_viaje_en_curso_sin_login(base_url, auth_headers):
    """El conductor nunca pasa por /auth/login — el token del QR reemplaza
    esa autenticación por completo para este flujo."""
    driver = _driver_con_qr(base_url, auth_headers)
    info = requests.get(f"{base_url}/fleet/despacho/{driver['id']}", params={"token": driver["qr_token"]}).json()

    r = requests.post(
        f"{base_url}/fleet/despacho/{driver['id']}",
        params={"token": driver["qr_token"]},
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
    # (created_by=None es la única diferencia — lo registró el conductor).
    admin_view = requests.get(f"{base_url}/fleet/trips/{body['trip']['id']}", headers=auth_headers)
    assert admin_view.status_code == 200
    assert admin_view.json()["created_by"] is None
    assert admin_view.json()["remission_guide"] == "GR-TEST-0001"

    requests.patch(f"{base_url}/fleet/trips/{body['trip']['id']}/cancel", headers=auth_headers)
