"""
Pruebas de integración del modelo de costos a través del gateway: los costos fijos y de personal
cargados por el admin llegan al tablero con el devengo esperado, el operador no los ve, el IVA neto
llega hasta la respuesta y las exportaciones traen la estructura del costo. Escriben y borran costos de
prueba; correrlas contra una base desechable (FLOTA_BASE_URL).
"""
import zipfile
from contextlib import contextmanager
from decimal import Decimal
from io import BytesIO

import requests

SEPTIEMBRE = {"date_from": "2026-09-01", "date_to": "2026-09-30"}  # 30 días


def _resumen(base_url, headers, **params):
    r = requests.get(f"{base_url}/reports/dashboard/summary", headers=headers, params={**SEPTIEMBRE, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _primero_activo(base_url, headers):
    vehiculo = requests.get(f"{base_url}/fleet/vehicles", headers=headers).json()[0]
    conductor = next(d for d in requests.get(f"{base_url}/fleet/drivers", headers=headers).json() if d["status"] == "activo")
    return vehiculo["id"], conductor["id"]


@contextmanager
def _costos_de_prueba(base_url, auth_headers, vehiculo_id, conductor_id):
    creados = []
    try:
        for ruta, cuerpo in (
            ("/fleet/fixed-costs", {"vehicle_id": vehiculo_id, "category": "depreciacion", "amount": "3650.00", "period": "anual", "valid_from": "2026-01-01", "notes": "EJEMPLO de prueba"}),
            ("/fleet/personnel-costs", {"driver_id": conductor_id, "concept": "sueldo", "amount": "730.00", "valid_from": "2026-01-01", "notes": "EJEMPLO de prueba"}),
        ):
            r = requests.post(f"{base_url}{ruta}", headers=auth_headers, json=cuerpo)
            assert r.status_code == 201, r.text
            creados.append((ruta, r.json()["id"]))
        yield
    finally:
        for ruta, id_ in creados:
            requests.delete(f"{base_url}{ruta}/{id_}", headers=auth_headers)


def test_los_costos_fijos_y_de_personal_llegan_al_tablero_del_admin_con_su_devengo(base_url, auth_headers):
    vehiculo_id, conductor_id = _primero_activo(base_url, auth_headers)
    antes = _resumen(base_url, auth_headers)["fleet_costs"]
    assert antes["fixed_included"] is True and antes["total_cost"] is not None
    with _costos_de_prueba(base_url, auth_headers, vehiculo_id, conductor_id):
        despues = _resumen(base_url, auth_headers)["fleet_costs"]
    # depreciación 3650/365 = 10 por día × 30 = 300,00 ; personal 730 × 12/365 = 24 por día × 30 = 720,00
    assert Decimal(despues["fixed_cost"]) - Decimal(antes["fixed_cost"]) == Decimal("1020.00")
    assert Decimal(despues["personnel_cost"]) - Decimal(antes["personnel_cost"]) == Decimal("720.00")
    assert Decimal(despues["total_cost"]) - Decimal(antes["total_cost"]) == Decimal("1020.00")
    assert Decimal(despues["variable_cost"]) == Decimal(antes["variable_cost"])  # los fijos no tocan los variables

    def depreciacion(f):
        return Decimal(next(c for c in f["composition"] if c["key"] == "depreciacion")["amount"])

    assert depreciacion(despues) - depreciacion(antes) == Decimal("300.00")


def test_el_costo_total_es_variable_mas_fijo_y_el_margen_no_depende_de_la_categoria(base_url, auth_headers):
    todo = _resumen(base_url, auth_headers)
    f = todo["fleet_costs"]
    assert Decimal(f["total_cost"]) == Decimal(f["variable_cost"]) + Decimal(f["fixed_cost"])
    assert Decimal(todo["fleet_total_cost"]) == Decimal(f["variable_cost"])  # gasto operativo = costo variable
    combustible = _resumen(base_url, auth_headers, category="combustible")
    assert Decimal(combustible["fleet_total_cost"]) < Decimal(todo["fleet_total_cost"])  # el total sí se acota
    assert combustible["fleet_total_margin"] == todo["fleet_total_margin"] and combustible["fleet_costs"] == f  # el margen no


def test_el_operador_ve_costos_variables_pero_no_fijos_ni_personal(base_url, auth_headers, operator_headers):
    vehiculo_id, conductor_id = _primero_activo(base_url, auth_headers)
    with _costos_de_prueba(base_url, auth_headers, vehiculo_id, conductor_id):
        r = _resumen(base_url, operator_headers)
        assert r["fixed_costs_omitted_reason"] == "rol" and r["unallocated_personnel_cost"] is None
        f = r["fleet_costs"]
        assert f["fixed_included"] is False and f["fixed_cost"] is None and f["total_cost"] is None and f["profit"] is None
        assert all(v["costs"]["fixed_cost"] is None for v in r["vehicles"])
        drivers = requests.get(f"{base_url}/reports/dashboard/drivers", headers=operator_headers, params=SEPTIEMBRE).json()
        assert drivers["personnel_included"] is False and all(d["personnel_cost"] is None for d in drivers["drivers"])
    assert requests.get(f"{base_url}/fleet/fixed-costs", headers=operator_headers).status_code == 403


def test_el_iva_neto_llega_hasta_la_respuesta_y_no_toca_los_costos_sin_tarifa(base_url, auth_headers):
    bruto, neto = _resumen(base_url, auth_headers), _resumen(base_url, auth_headers, iva_mode="neto")
    assert (bruto["iva_mode"], neto["iva_mode"]) == ("bruto", "neto")
    assert Decimal(neto["fleet_costs"]["variable_cost"]) < Decimal(bruto["fleet_costs"]["variable_cost"])  # combustible, alimentación y mantenimiento pierden el 15 %
    assert neto["fleet_costs"]["fixed_cost"] == bruto["fleet_costs"]["fixed_cost"]  # fijos y personal: tarifa 0 en iva_config.json
    assert neto["fleet_total_revenue"] == bruto["fleet_total_revenue"]

    def suma(r, campo):
        return sum(Decimal(v["breakdown"][campo]) for v in r["vehicles"])

    assert suma(neto, "peaje") == suma(bruto, "peaje")  # tarifa 0
    # combustible: 15 % (comprobantes del SRI); cada vehículo se redondea a centavos, de ahí la tolerancia
    assert abs(suma(neto, "combustible") - suma(bruto, "combustible") / Decimal("1.15")) <= Decimal("0.01") * len(neto["vehicles"])
    for ruta in ("/reports/dashboard/trend", "/reports/dashboard/routes", "/reports/dashboard/drivers", "/reports/dashboard/records"):
        assert requests.get(f"{base_url}{ruta}", headers=auth_headers, params={**SEPTIEMBRE, "iva_mode": "neto"}).status_code == 200, ruta
        assert requests.get(f"{base_url}{ruta}", headers=auth_headers, params={**SEPTIEMBRE, "iva_mode": "gravado"}).status_code == 422, ruta


def test_la_metodologia_y_las_exportaciones(base_url, auth_headers):
    m = requests.get(f"{base_url}/reports/dashboard/cost-model", headers=auth_headers).json()
    assert len(m["categories"]) == 8 and m["iva"]["estado"] == "pendiente_de_verificacion_contable"
    xlsx = requests.get(f"{base_url}/reports/reports/costs.xlsx", headers=auth_headers, params={**SEPTIEMBRE, "iva_mode": "neto"})
    assert xlsx.status_code == 200
    with zipfile.ZipFile(BytesIO(xlsx.content)) as z:
        libro = z.read("xl/workbook.xml").decode("utf-8")
    assert "Estructura de costos" in libro and "Notas" in libro
    pdf = requests.get(f"{base_url}/reports/reports/costs.pdf", headers=auth_headers, params=SEPTIEMBRE)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
