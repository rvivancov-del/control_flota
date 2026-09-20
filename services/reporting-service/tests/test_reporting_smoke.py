"""
Pruebas de integración contra el stack real (gateway en localhost:8080).
Requieren `docker compose up` corriendo, con datos sembrados. Cubren
RF-15, RF-16, RF-17. reporting-service no tiene base de datos propia —
agrega llamando a fleet-core-service, así que estas pruebas también
verifican que esa integración entre servicios funcione de punta a punta.
"""
import requests


def test_resumen_del_dashboard(base_url, auth_headers):
    r = requests.get(f"{base_url}/reports/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "fleet_total_cost" in body
    assert "vehicles" in body
    assert len(body["vehicles"]) > 0


def test_tendencia_por_mes(base_url, auth_headers):
    r = requests.get(f"{base_url}/reports/dashboard/trend", headers=auth_headers, params={"period": "month"})
    assert r.status_code == 200
    assert "points" in r.json()


def test_costo_por_ruta(base_url, auth_headers):
    r = requests.get(f"{base_url}/reports/dashboard/routes", headers=auth_headers)
    assert r.status_code == 200
    assert "routes" in r.json()


def test_estado_de_mantenimiento(base_url, auth_headers):
    r = requests.get(f"{base_url}/reports/dashboard/maintenance-status", headers=auth_headers)
    assert r.status_code == 200


def test_prioridad_de_mantenimiento_ahp(base_url, auth_headers):
    """RF-20: el ranking AHP debe venir ordenado de mayor a menor prioridad,
    y los pesos de criterios deben ser consistentes (CR < 0.10) — si esto
    falla, revisar PAIRWISE_MATRIX en app/dashboards/ahp.py."""
    r = requests.get(f"{base_url}/reports/dashboard/maintenance-priority", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["weights"]["is_consistent"] is True
    assert body["weights"]["consistency_ratio"] < 0.10
    scores = [item["priority_score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)


def test_exportar_reporte_excel(base_url, auth_headers):
    """RF-17: el archivo debe ser un .xlsx real, no un JSON de error disfrazado.
    La ruta real es /reports/reports/costs.xlsx (el segmento se duplica porque
    el router interno ya empieza en /reports/... y el gateway agrega otro
    /api/reports/ encima — así la llama también el frontend, en reportsApi.ts)."""
    r = requests.get(f"{base_url}/reports/reports/costs.xlsx", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(r.content) > 100
