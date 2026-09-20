"""
Pruebas de integración contra el stack real (gateway en localhost:8080).
Requieren `docker compose up` corriendo, con al menos un año de datos
sembrados (ver scripts de seed usados en desarrollo). Cubren RF-04 a RF-14.
"""
from datetime import datetime, timedelta, timezone

import requests


def test_listar_vehiculos(base_url, auth_headers):
    r = requests.get(f"{base_url}/fleet/vehicles", headers=auth_headers)
    assert r.status_code == 200
    vehicles = r.json()
    assert isinstance(vehicles, list)
    assert len(vehicles) > 0
    assert "plate" in vehicles[0]


def test_listar_conductores(base_url, auth_headers):
    r = requests.get(f"{base_url}/fleet/drivers", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_alertas_de_mantenimiento(base_url, auth_headers):
    r = requests.get(f"{base_url}/fleet/maintenance/alerts", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_ciclo_completo_de_viaje(base_url, auth_headers):
    """RF-06 (registrar) + RF-07 (cerrar, con cálculo real de kilometraje)."""
    vehicle = requests.get(f"{base_url}/fleet/vehicles", headers=auth_headers).json()[0]
    driver = requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).json()[0]
    start_km = vehicle["current_mileage_km"]

    create = requests.post(
        f"{base_url}/fleet/trips",
        headers=auth_headers,
        json={
            "vehicle_id": vehicle["id"],
            "driver_id": driver["id"],
            "origin": "Guayaquil",
            "destination": "Quito",
            "departure_at": datetime.now(timezone.utc).isoformat(),
            "start_mileage_km": start_km,
        },
    )
    assert create.status_code == 201
    trip = create.json()
    assert trip["status"] == "planificado"

    started = requests.patch(f"{base_url}/fleet/trips/{trip['id']}/start", headers=auth_headers)
    assert started.status_code == 200
    assert started.json()["status"] == "en_curso"

    end_km = start_km + 250
    closed = requests.patch(
        f"{base_url}/fleet/trips/{trip['id']}/close",
        headers=auth_headers,
        json={
            "end_mileage_km": end_km,
            "arrival_at": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
            "revenue": 300.50,
        },
    )
    assert closed.status_code == 200
    result = closed.json()
    assert result["trip"]["status"] == "completado"
    assert result["trip"]["km_recorridos"] == 250
    assert result["trip"]["revenue"] == "300.50"

    expense = requests.post(
        f"{base_url}/fleet/trips/{trip['id']}/expenses",
        headers=auth_headers,
        json={"type": "combustible", "amount": 80.00, "expense_date": datetime.now(timezone.utc).date().isoformat(), "liters": 95.0},
    )
    assert expense.status_code == 201
    assert expense.json()["liters"] == "95.00"

    expenses = requests.get(f"{base_url}/fleet/trips/{trip['id']}/expenses", headers=auth_headers)
    assert expenses.status_code == 200
    assert len(expenses.json()) == 1
