"""
Pruebas de integración de los costos fijos y de personal contra el stack real: CRUD solo admin,
devengo prorrateado por días verificado con cálculos hechos a mano, y validaciones. Crean registros de
prueba y los borran al terminar; correrlas contra una base desechable (FLOTA_BASE_URL).
"""
import uuid
from contextlib import contextmanager
from decimal import Decimal

import pytest
import requests

SEPTIEMBRE = {"date_from": "2026-09-01", "date_to": "2026-09-30"}  # 30 días


def _admin(base_url, auth_headers):
    return lambda method, path, **kw: requests.request(method, f"{base_url}/fleet{path}", headers=auth_headers, **kw)


@pytest.fixture(scope="module")
def vehiculo(base_url, auth_headers):
    return requests.get(f"{base_url}/fleet/vehicles", headers=auth_headers).json()[0]


@pytest.fixture(scope="module")
def conductor(base_url, auth_headers):
    return next(d for d in requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).json() if d["status"] == "activo")


@contextmanager
def _registro(api, ruta, payload):
    """Crea un registro y lo borra al salir, pase lo que pase."""
    r = api("POST", ruta, json=payload)
    assert r.status_code == 201, r.text
    creado = r.json()
    try:
        yield creado
    finally:
        api("DELETE", f"{ruta}/{creado['id']}")


def _devengo(api, ruta, clave, valor, categoria, **periodo):
    filas = api("GET", ruta, params=periodo or SEPTIEMBRE).json()
    return sum(Decimal(f["amount"]) for f in filas if f[clave] == valor and f["category" if "fixed" in ruta else "concept"] == categoria)


def test_costo_fijo_anual_se_devenga_por_dias(base_url, auth_headers, vehiculo):
    api = _admin(base_url, auth_headers)
    with _registro(api, "/fixed-costs", {"vehicle_id": vehiculo["id"], "category": "seguro", "amount": "3650.00", "period": "anual", "valid_from": "2026-01-01"}):
        # 3650 / 365 = 10 por día × 30 días de septiembre = 300,00
        assert _devengo(api, "/analytics/fixed-costs", "vehicle_id", vehiculo["id"], "seguro") == Decimal("300.00")
        # solo 10 días del período: 100,00
        assert _devengo(api, "/analytics/fixed-costs", "vehicle_id", vehiculo["id"], "seguro", date_from="2026-09-01", date_to="2026-09-10") == Decimal("100.00")
    assert _devengo(api, "/analytics/fixed-costs", "vehicle_id", vehiculo["id"], "seguro") == Decimal("0")  # borrado: ya no devenga


def test_costo_fijo_mensual_se_prorratea_con_365_dias(base_url, auth_headers, vehiculo):
    api = _admin(base_url, auth_headers)
    with _registro(api, "/fixed-costs", {"vehicle_id": vehiculo["id"], "category": "capital", "amount": "300.00", "period": "mensual", "valid_from": "2026-01-01"}):
        # 300 × 12 / 365 = 9,8630… por día × 30 = 295,89 (no 300,00: el mes calendario tiene 30 de 365/12 = 30,42 días)
        assert _devengo(api, "/analytics/fixed-costs", "vehicle_id", vehiculo["id"], "capital") == Decimal("295.89")
        # un año completo devenga exactamente 12 meses
        assert _devengo(api, "/analytics/fixed-costs", "vehicle_id", vehiculo["id"], "capital", date_from="2026-01-01", date_to="2026-12-31") == Decimal("3600.00")


def test_la_vigencia_limita_el_devengo_y_los_tramos_se_suman(base_url, auth_headers, vehiculo):
    api = _admin(base_url, auth_headers)
    with _registro(api, "/fixed-costs", {"vehicle_id": vehiculo["id"], "category": "otros", "amount": "3650.00", "period": "anual", "valid_from": "2026-01-01", "valid_to": "2026-09-14"}), \
         _registro(api, "/fixed-costs", {"vehicle_id": vehiculo["id"], "category": "otros", "amount": "7300.00", "period": "anual", "valid_from": "2026-09-15"}):
        # tramo 1: 14 días × 10 = 140 ; tramo 2: 16 días × 20 = 320 ; suma 460,00
        assert _devengo(api, "/analytics/fixed-costs", "vehicle_id", vehiculo["id"], "otros") == Decimal("460.00")
        # un período que no toca ninguna vigencia no devenga nada
        assert _devengo(api, "/analytics/fixed-costs", "vehicle_id", vehiculo["id"], "otros", date_from="2025-01-01", date_to="2025-12-31") == Decimal("0")


def test_costo_de_personal_mensual_se_devenga_por_dias(base_url, auth_headers, conductor):
    api = _admin(base_url, auth_headers)
    with _registro(api, "/personnel-costs", {"driver_id": conductor["id"], "concept": "sueldo", "amount": "730.00", "valid_from": "2026-01-01"}), \
         _registro(api, "/personnel-costs", {"driver_id": conductor["id"], "concept": "beneficios_sociales", "amount": "365.00", "valid_from": "2026-01-01"}):
        # 730 × 12 / 365 = 24 por día × 10 días = 240,00 ; 365 × 12 / 365 = 12 por día × 10 = 120,00
        p10 = dict(date_from="2026-09-01", date_to="2026-09-10")
        assert _devengo(api, "/analytics/personnel-costs", "driver_id", conductor["id"], "sueldo", **p10) == Decimal("240.00")
        assert _devengo(api, "/analytics/personnel-costs", "driver_id", conductor["id"], "beneficios_sociales", **p10) == Decimal("120.00")


def test_el_crud_edita_y_borra(base_url, auth_headers, vehiculo):
    api = _admin(base_url, auth_headers)
    payload = {"vehicle_id": vehiculo["id"], "category": "impuestos", "amount": "120.00", "period": "anual", "valid_from": "2026-01-01", "notes": "EJEMPLO de prueba"}
    r = api("POST", "/fixed-costs", json=payload)
    assert r.status_code == 201
    costo = r.json()
    assert costo["amount"] == "120.00" and costo["valid_to"] is None
    assert costo["id"] in {c["id"] for c in api("GET", "/fixed-costs", params={"vehicle_id": vehiculo["id"]}).json()}
    editado = api("PATCH", f"/fixed-costs/{costo['id']}", json={"amount": "240.00", "valid_to": "2026-12-31"})
    assert editado.status_code == 200 and editado.json()["amount"] == "240.00" and editado.json()["valid_to"] == "2026-12-31"
    assert api("DELETE", f"/fixed-costs/{costo['id']}").status_code == 204
    assert api("DELETE", f"/fixed-costs/{costo['id']}").status_code == 404
    assert api("PATCH", f"/fixed-costs/{costo['id']}", json={"amount": "1.00"}).status_code == 404


def test_validaciones_de_los_costos(base_url, auth_headers, vehiculo, conductor):
    api = _admin(base_url, auth_headers)
    base = {"vehicle_id": vehiculo["id"], "category": "seguro", "amount": "100.00", "period": "anual", "valid_from": "2026-01-01"}
    inexistente = "00000000-0000-0000-0000-000000000000"
    casos = [
        ("/fixed-costs", {**base, "vehicle_id": inexistente}),
        ("/fixed-costs", {**base, "category": "combustible"}),
        ("/fixed-costs", {**base, "period": "semanal"}),
        ("/fixed-costs", {**base, "amount": "0"}),
        ("/fixed-costs", {**base, "amount": "-5"}),
        ("/fixed-costs", {**base, "valid_to": "2025-12-31"}),
        ("/personnel-costs", {"driver_id": inexistente, "concept": "sueldo", "amount": "500", "valid_from": "2026-01-01"}),
        ("/personnel-costs", {"driver_id": conductor["id"], "concept": "bono", "amount": "500", "valid_from": "2026-01-01"}),
        ("/personnel-costs", {"driver_id": conductor["id"], "concept": "sueldo", "amount": "0", "valid_from": "2026-01-01"}),
    ]
    for ruta, cuerpo in casos:
        assert api("POST", ruta, json=cuerpo).status_code == 422, (ruta, cuerpo)
    with _registro(api, "/fixed-costs", base) as c:  # editar dejando la vigencia al revés se rechaza
        assert api("PATCH", f"/fixed-costs/{c['id']}", json={"valid_to": "2025-06-01"}).status_code == 422
    for ruta in ("/analytics/fixed-costs", "/analytics/personnel-costs"):
        assert api("GET", ruta).status_code == 422  # sin período no hay nada que prorratear
        assert api("GET", ruta, params={"date_from": "2026-09-30", "date_to": "2026-09-01"}).status_code == 422


def test_no_se_registra_personal_a_un_conductor_con_datos_suprimidos(base_url, auth_headers):
    api = _admin(base_url, auth_headers)
    nuevo = api("POST", "/drivers", json={"full_name": "Persona Costos", "license_number": f"COSTOS-{uuid.uuid4().hex[:8]}"})
    assert nuevo.status_code == 201, nuevo.text
    driver_id = nuevo.json()["id"]
    assert api("POST", f"/drivers/{driver_id}/anonymize").status_code == 200
    r = api("POST", "/personnel-costs", json={"driver_id": driver_id, "concept": "sueldo", "amount": "500", "valid_from": "2026-01-01"})
    assert r.status_code == 409 and "suprimidos" in r.text


def test_el_operador_no_ve_ni_administra_costos_fijos(base_url, auth_headers, operator_headers, vehiculo, conductor):
    admin = _admin(base_url, auth_headers)
    antes = (len(admin("GET", "/fixed-costs").json()), len(admin("GET", "/personnel-costs").json()))
    op = lambda method, path, **kw: requests.request(method, f"{base_url}/fleet{path}", headers=operator_headers, **kw)
    nuevo_fijo = {"vehicle_id": vehiculo["id"], "category": "seguro", "amount": "100.00", "period": "anual", "valid_from": "2026-01-01"}
    nuevo_personal = {"driver_id": conductor["id"], "concept": "sueldo", "amount": "500.00", "valid_from": "2026-01-01"}
    intentos = [
        op("GET", "/fixed-costs"), op("POST", "/fixed-costs", json=nuevo_fijo),
        op("GET", "/personnel-costs"), op("POST", "/personnel-costs", json=nuevo_personal),
        op("GET", "/analytics/fixed-costs", params=SEPTIEMBRE), op("GET", "/analytics/personnel-costs", params=SEPTIEMBRE),
    ]
    assert [r.status_code for r in intentos] == [403] * 6
    assert (len(admin("GET", "/fixed-costs").json()), len(admin("GET", "/personnel-costs").json())) == antes


def test_los_agregados_de_viajes_y_rutas_traen_cobertura_de_ingresos_y_gasto_por_tipo(base_url, auth_headers):
    viajes = requests.get(f"{base_url}/fleet/analytics/trips", headers=auth_headers).json()
    assert viajes and all({"revenue_trip_count", "revenue_distance_km"} <= set(v) for v in viajes)
    assert all(v["revenue_distance_km"] <= v["distance_km"] for v in viajes)
    rutas = requests.get(f"{base_url}/fleet/analytics/routes", headers=auth_headers).json()
    assert rutas
    for r in rutas:
        por_tipo = Decimal(r["cost_combustible"]) + Decimal(r["cost_peaje"]) + Decimal(r["cost_alimentacion"])
        assert por_tipo == Decimal(r["cost_total"]), r
