"""
Pruebas de integración de GET /maintenance (Fase 5): el historial de mantenimientos de toda la flota
en una sola consulta debe coincidir, registro por registro, con lo que devuelve el historial de cada
vehículo por separado, y aceptar sus filtros. Solo leen datos.
"""
import pytest
import requests


def _get(base_url, headers, path, **params):
    return requests.get(f"{base_url}/fleet{path}", headers=headers, params=params)


@pytest.fixture(scope="module")
def por_vehiculo(base_url, auth_headers):
    """El historial pedido vehículo por vehículo: la referencia contra la que se compara."""
    vehiculos = _get(base_url, auth_headers, "/vehicles").json()
    registros = []
    for v in vehiculos:
        r = _get(base_url, auth_headers, f"/vehicles/{v['id']}/maintenance")
        assert r.status_code == 200, r.text
        registros.extend(r.json())
    return registros


def test_la_lista_de_la_flota_coincide_con_la_suma_de_los_historiales(base_url, auth_headers, por_vehiculo):
    r = _get(base_url, auth_headers, "/maintenance")
    assert r.status_code == 200, r.text
    todos = r.json()
    assert len(todos) == len(por_vehiculo) > 0, "la base piloto trae mantenimientos: la comparación no puede ser vacía"
    # mismos registros, con los mismos campos calculados (km restantes y urgencia incluidos)
    assert sorted(todos, key=lambda x: x["id"]) == sorted(por_vehiculo, key=lambda x: x["id"])


def test_viene_del_mas_reciente_al_mas_antiguo(base_url, auth_headers):
    creados = [x["created_at"] for x in _get(base_url, auth_headers, "/maintenance").json()]
    assert creados == sorted(creados, reverse=True)


def test_filtra_por_vehiculo(base_url, auth_headers, por_vehiculo):
    vid = por_vehiculo[0]["vehicle_id"]
    r = _get(base_url, auth_headers, "/maintenance", vehicle_id=vid)
    assert r.status_code == 200
    esperados = {x["id"] for x in por_vehiculo if x["vehicle_id"] == vid}
    assert {x["id"] for x in r.json()} == esperados


@pytest.mark.parametrize("estado", ["pendiente", "completado"])
def test_filtra_por_estado(base_url, auth_headers, por_vehiculo, estado):
    r = _get(base_url, auth_headers, "/maintenance", status_filter=estado)
    assert r.status_code == 200
    esperados = {x["id"] for x in por_vehiculo if x["status"] == estado}
    assert {x["id"] for x in r.json()} == esperados


def test_un_estado_desconocido_es_un_error_del_cliente(base_url, auth_headers):
    r = _get(base_url, auth_headers, "/maintenance", status_filter="inventado")
    assert r.status_code == 422
    assert "status_filter" in r.text


def test_sin_sesion_no_hay_acceso(base_url):
    assert requests.get(f"{base_url}/fleet/maintenance").status_code in (401, 403)


def test_el_operador_tambien_lo_consulta(base_url, operator_headers):
    assert requests.get(f"{base_url}/fleet/maintenance", headers=operator_headers).status_code == 200
