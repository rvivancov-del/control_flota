"""
Pruebas de integración de los permisos por rol (RF-03) de reporting-service contra
el stack real, con una sesión de operador de verdad. La matriz completa está en
test_roles.py. Las rutas llevan el segmento /reports/ duplicado (ver
test_reporting_smoke.py::test_exportar_reporte_excel).
"""
import requests


def test_el_operador_consulta_el_tablero_y_los_reportes_en_pantalla(base_url, operator_headers):
    for ruta in (
        "/reports/dashboard/summary",
        "/reports/dashboard/trend?period=month",
        "/reports/dashboard/routes",
        "/reports/dashboard/maintenance-status",
        "/reports/dashboard/maintenance-priority",
        "/reports/dashboard/vehicle-attention",
        "/reports/reports/maintenance",
    ):
        assert requests.get(f"{base_url}{ruta}", headers=operator_headers).status_code == 200, ruta


def test_el_operador_no_puede_exportar_reportes(base_url, operator_headers):
    for ruta in ("/reports/reports/costs.xlsx", "/reports/reports/costs.pdf"):
        r = requests.get(f"{base_url}{ruta}", headers=operator_headers)
        assert r.status_code == 403, ruta
        assert "spreadsheet" not in r.headers.get("Content-Type", "") and "pdf" not in r.headers.get("Content-Type", "")


def test_el_admin_si_exporta_reportes(base_url, auth_headers):
    xlsx = requests.get(f"{base_url}/reports/reports/costs.xlsx", headers=auth_headers)
    pdf = requests.get(f"{base_url}/reports/reports/costs.pdf", headers=auth_headers)
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
