"""Pruebas del router de costos (Fase 3): quién ve los costos fijos y de personal, validación de
iva_mode y el endpoint de metodología. Usa el escenario de test_costs_service.py con un cliente de
fleet-core simulado; no requiere el stack."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core import security
from app.dashboards import router as dashboards_router
from app.main import app
from tests.test_costs_service import FakeFleet

PERIODO = {"date_from": "2026-09-01", "date_to": "2026-09-30"}


def _token(role: str) -> dict:
    payload = {"sub": str(uuid.uuid4()), "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return {"Authorization": "Bearer " + jwt.encode(payload, security.JWT_SECRET_KEY, algorithm=security.JWT_ALGORITHM)}


@pytest.fixture()
def cliente():
    """Devuelve una función que arma el cliente con el FakeFleet indicado."""

    def _armar(allow_fixed: bool):
        fleet = FakeFleet(allow_fixed=allow_fixed)
        app.dependency_overrides[dashboards_router._fleet_client] = lambda: fleet
        return TestClient(app, raise_server_exceptions=False), fleet

    yield _armar
    app.dependency_overrides.clear()


def test_el_admin_recibe_costos_fijos_y_de_personal_en_el_resumen(cliente):
    c, fleet = cliente(True)
    r = c.get("/dashboard/summary", params=PERIODO, headers=_token("admin"))
    assert r.status_code == 200
    body = r.json()
    assert body["fleet_costs"]["fixed_included"] is True and body["fleet_costs"]["total_cost"] == "1430.00"
    assert body["fixed_costs_omitted_reason"] is None and fleet.fixed_calls == 2


def test_el_operador_no_recibe_costos_fijos_ni_se_piden_a_fleet_core(cliente):
    c, fleet = cliente(False)  # el FakeFleet falla si alguien pide costos fijos sin permiso
    r = c.get("/dashboard/summary", params=PERIODO, headers=_token("operador"))
    assert r.status_code == 200
    body = r.json()
    assert body["fleet_costs"]["fixed_included"] is False and body["fleet_costs"]["total_cost"] is None
    assert body["fixed_costs_omitted_reason"] == "rol" and fleet.fixed_calls == 0
    assert body["fleet_costs"]["variable_cost"] == "500.00"


def test_el_operador_tampoco_ve_los_sueldos_por_conductor(cliente):
    c, fleet = cliente(False)
    body = c.get("/dashboard/drivers", params=PERIODO, headers=_token("operador")).json()
    assert body["personnel_included"] is False and all(d["personnel_cost"] is None for d in body["drivers"])
    assert fleet.fixed_calls == 0
    admin = cliente(True)[0].get("/dashboard/drivers", params=PERIODO, headers=_token("admin")).json()
    assert admin["personnel_included"] is True and {d["personnel_cost"] for d in admin["drivers"]} == {"400.00", "200.00", "100.00"}


def test_sin_periodo_el_admin_tampoco_recibe_costos_fijos(cliente):
    c, fleet = cliente(True)
    body = c.get("/dashboard/summary", headers=_token("admin")).json()
    assert body["fixed_costs_omitted_reason"] == "sin_periodo" and fleet.fixed_calls == 0


@pytest.mark.parametrize("ruta", ["/dashboard/summary", "/dashboard/trend", "/dashboard/records", "/dashboard/drivers", "/dashboard/routes",
                                  "/dashboard/maintenance-status", "/reports/maintenance"])
def test_un_modo_de_iva_invalido_se_rechaza_en_cada_endpoint_de_costos(cliente, ruta):
    c, _ = cliente(True)
    r = c.get(ruta, params={**PERIODO, "iva_mode": "gravado"}, headers=_token("admin"))
    assert r.status_code == 422 and "iva_mode" in r.text


def test_el_modo_de_iva_se_aplica_y_por_defecto_es_bruto(cliente):
    c, _ = cliente(True)
    assert c.get("/dashboard/summary", params=PERIODO, headers=_token("admin")).json()["iva_mode"] == "bruto"
    neto = c.get("/dashboard/summary", params={**PERIODO, "iva_mode": "neto"}, headers=_token("admin")).json()
    assert neto["iva_mode"] == "neto" and float(neto["fleet_costs"]["variable_cost"]) < 500  # sin el IVA de alimentación y mantenimiento


def test_las_exportaciones_del_admin_incluyen_los_costos_fijos(cliente):
    c, fleet = cliente(True)
    xlsx = c.get("/reports/costs.xlsx", params=PERIODO, headers=_token("admin"))
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK" and fleet.fixed_calls == 2
    pdf = c.get("/reports/costs.pdf", params={**PERIODO, "iva_mode": "neto"}, headers=_token("admin"))
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert c.get("/reports/costs.xlsx", params=PERIODO, headers=_token("operador")).status_code == 403


def test_la_metodologia_del_modelo_de_costos_esta_disponible_para_ambos_roles(cliente):
    c, _ = cliente(False)
    for rol in ("admin", "operador"):
        r = c.get("/dashboard/cost-model", headers=_token(rol))
        assert r.status_code == 200
        body = r.json()
        assert [x["key"] for x in body["categories"]][:3] == ["combustible", "reparaciones", "depreciacion"] and len(body["categories"]) == 8
        assert {i["id"] for i in body["indicators"]} >= {"Cv", "Cf", "Ct", "LP", "ROP", "IVA neto"}
        assert body["iva"]["estado"] == "pendiente_de_verificacion_contable" and body["iva"]["modo_por_defecto"] == "bruto"
        assert body["iva"]["tarifas"]["mantenimiento"] == 0.15
