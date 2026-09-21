"""
Pruebas de integración de los filtros de consulta (RF-14), la ubicación del peaje (RF-09),
la validación de licencia y estados (RF-05) y la supresión de datos personales (RNF-11)
contra el stack real. Escriben datos (conductores, viajes, gastos de prueba): correrlas
contra una base desechable (FLOTA_BASE_URL).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests


def _get(base_url, headers, path, **params):
    r = requests.get(f"{base_url}{path}", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def datos(base_url, auth_headers):
    vehiculos = _get(base_url, auth_headers, "/fleet/vehicles")
    conductores = _get(base_url, auth_headers, "/fleet/drivers")
    viajes = _get(base_url, auth_headers, "/fleet/trips")
    return {"vehiculos": vehiculos, "conductores": conductores, "viajes": viajes}


def _crear_viaje(base_url, headers, vehiculo, conductor, salida=None, km=None):
    r = requests.post(
        f"{base_url}/fleet/trips",
        headers=headers,
        json={
            "vehicle_id": vehiculo["id"],
            "driver_id": conductor["id"],
            "origin": "Guayaquil",
            "destination": "Cuenca",
            "departure_at": (salida or datetime.now(timezone.utc)).isoformat(),
            "start_mileage_km": vehiculo["current_mileage_km"] if km is None else km,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ RF-14: viajes
def test_filtrar_viajes_por_rango_de_fechas_coincide_con_el_calculo_manual(base_url, auth_headers, datos):
    fechas = sorted({v["departure_at"][:10] for v in datos["viajes"]})
    desde, hasta = fechas[len(fechas) // 3], fechas[2 * len(fechas) // 3]
    esperados = {v["id"] for v in datos["viajes"] if desde <= v["departure_at"][:10] <= hasta}
    obtenidos = _get(base_url, auth_headers, "/fleet/trips", date_from=desde, date_to=hasta)
    assert esperados and {v["id"] for v in obtenidos} == esperados
    assert len(esperados) < len(datos["viajes"])


def test_filtrar_viajes_combina_vehiculo_conductor_estado_y_fechas(base_url, auth_headers, datos):
    viaje = next(v for v in datos["viajes"] if v["status"] == "completado")
    dia = viaje["departure_at"][:10]
    obtenidos = _get(
        base_url, auth_headers, "/fleet/trips",
        vehicle_id=viaje["vehicle_id"], driver_id=viaje["driver_id"], status_filter="completado", date_from=dia, date_to=dia,
    )
    assert viaje["id"] in {v["id"] for v in obtenidos}
    assert all(
        v["vehicle_id"] == viaje["vehicle_id"] and v["driver_id"] == viaje["driver_id"]
        and v["status"] == "completado" and v["departure_at"][:10] == dia
        for v in obtenidos
    )


def test_un_rango_de_fechas_invalido_o_un_estado_desconocido_se_rechazan(base_url, auth_headers):
    r = requests.get(f"{base_url}/fleet/trips", headers=auth_headers, params={"date_from": "2026-09-10", "date_to": "2026-09-01"})
    assert r.status_code == 422 and "date_from" in r.text
    assert requests.get(f"{base_url}/fleet/trips", headers=auth_headers, params={"status_filter": "volando"}).status_code == 422
    assert requests.get(f"{base_url}/fleet/trips", headers=auth_headers, params={"date_from": "no-es-fecha"}).status_code == 422


# ------------------------------------------------------------------ RF-14: gastos
def test_consultar_gastos_por_vehiculo_y_fechas_coincide_con_los_gastos_de_sus_viajes(base_url, auth_headers, datos):
    vehiculo = max(datos["vehiculos"], key=lambda v: sum(t["vehicle_id"] == v["id"] for t in datos["viajes"]))
    viajes_v = [t for t in datos["viajes"] if t["vehicle_id"] == vehiculo["id"]]
    por_viaje = []
    for t in viajes_v:
        por_viaje += _get(base_url, auth_headers, f"/fleet/trips/{t['id']}/expenses")
    fechas = sorted({e["expense_date"] for e in por_viaje})
    desde, hasta = fechas[len(fechas) // 4], fechas[3 * len(fechas) // 4]
    esperados = {e["id"] for e in por_viaje if desde <= e["expense_date"] <= hasta}

    obtenidos = _get(base_url, auth_headers, "/fleet/expenses", vehicle_id=vehiculo["id"], date_from=desde, date_to=hasta)
    assert esperados and {e["id"] for e in obtenidos} == esperados
    assert all(e["vehicle_id"] == vehiculo["id"] and desde <= e["expense_date"] <= hasta for e in obtenidos)
    assert all({"driver_id", "origin", "destination", "location"} <= set(e) for e in obtenidos)
    assert [e["expense_date"] for e in obtenidos] == sorted((e["expense_date"] for e in obtenidos), reverse=True)


def test_consultar_gastos_por_conductor_tipo_y_limite(base_url, auth_headers, datos):
    conductor = next(d for d in datos["conductores"] if any(t["driver_id"] == d["id"] for t in datos["viajes"]))
    obtenidos = _get(base_url, auth_headers, "/fleet/expenses", driver_id=conductor["id"], type="peaje")
    assert obtenidos and all(e["driver_id"] == conductor["id"] and e["type"] == "peaje" for e in obtenidos)
    assert len(_get(base_url, auth_headers, "/fleet/expenses", limit=3)) == 3


def test_consultar_gastos_rechaza_filtros_invalidos(base_url, auth_headers):
    for params in ({"type": "hospedaje"}, {"date_from": "2026-09-10", "date_to": "2026-09-01"}, {"limit": 0}, {"limit": 999999}):
        assert requests.get(f"{base_url}/fleet/expenses", headers=auth_headers, params=params).status_code == 422, params


# ------------------------------------------------------------------ RF-09: ubicación del peaje
def test_el_peaje_exige_ubicacion_y_se_puede_corregir(base_url, auth_headers, datos):
    vehiculo, conductor = datos["vehiculos"][0], datos["conductores"][0]
    viaje = _crear_viaje(base_url, auth_headers, vehiculo, conductor)
    url = f"{base_url}/fleet/trips/{viaje['id']}/expenses"
    hoy = datetime.now(timezone.utc).date().isoformat()

    sin_ubicacion = requests.post(url, headers=auth_headers, json={"type": "peaje", "amount": "2.50", "expense_date": hoy})
    assert sin_ubicacion.status_code == 422 and "location" in sin_ubicacion.text
    en_blanco = requests.post(url, headers=auth_headers, json={"type": "peaje", "amount": "2.50", "expense_date": hoy, "location": "  "})
    assert en_blanco.status_code == 422

    creado = requests.post(url, headers=auth_headers, json={"type": "peaje", "amount": "2.50", "expense_date": hoy, "location": " Peaje Nueva Esperanza "})
    assert creado.status_code == 201 and creado.json()["location"] == "Peaje Nueva Esperanza"
    gasto_id = creado.json()["id"]
    assert [e["location"] for e in _get(base_url, auth_headers, f"/fleet/trips/{viaje['id']}/expenses")] == ["Peaje Nueva Esperanza"]

    corregido = requests.patch(f"{url}/{gasto_id}", headers=auth_headers, json={"location": "Peaje Santa Lucía"})
    assert corregido.status_code == 200 and corregido.json()["location"] == "Peaje Santa Lucía"
    vacio = requests.patch(f"{url}/{gasto_id}", headers=auth_headers, json={"location": "  "})
    assert vacio.status_code == 422

    # la ubicación solo aplica a peajes: en otro tipo se descarta al crear y no se puede editar
    comida = requests.post(url, headers=auth_headers, json={"type": "alimentacion", "amount": "6.00", "expense_date": hoy, "location": "Guayaquil"})
    assert comida.status_code == 201 and comida.json()["location"] is None
    assert requests.patch(f"{url}/{comida.json()['id']}", headers=auth_headers, json={"location": "Guayaquil"}).status_code == 422

    # montos y litros no positivos
    assert requests.post(url, headers=auth_headers, json={"type": "combustible", "amount": "0", "expense_date": hoy}).status_code == 422
    requests.patch(f"{base_url}/fleet/trips/{viaje['id']}/cancel", headers=auth_headers)


# ------------------------------------------------------------------ RF-05: licencia y estados
def test_tipos_de_licencia_disponibles_para_el_formulario(base_url, auth_headers):
    tipos = _get(base_url, auth_headers, "/fleet/drivers/license-types")
    assert {t["code"] for t in tipos} == {"A", "A1", "B", "C", "C1", "D", "E", "F", "G"}
    assert "camiones pesados" in next(t for t in tipos if t["code"] == "E")["description"]


def test_los_datos_existentes_quedaron_normalizados(base_url, auth_headers, datos):
    validos = {"A", "A1", "B", "C", "C1", "D", "E", "F", "G"}
    assert all(d["license_type"] is None or d["license_type"] in validos for d in datos["conductores"])


def test_la_licencia_y_los_estados_se_validan_al_guardar(base_url, auth_headers, datos):
    conductor, vehiculo = datos["conductores"][0], datos["vehiculos"][0]
    antes = (conductor["license_type"], conductor["status"], vehiculo["status"])
    nuevo = {"full_name": "Prueba Licencia", "license_number": f"LIC-{uuid.uuid4().hex[:8]}"}

    assert requests.post(f"{base_url}/fleet/drivers", headers=auth_headers, json={**nuevo, "license_type": "Z"}).status_code == 422
    assert requests.patch(f"{base_url}/fleet/drivers/{conductor['id']}", headers=auth_headers, json={"license_type": "Z"}).status_code == 422
    assert requests.patch(f"{base_url}/fleet/drivers/{conductor['id']}", headers=auth_headers, json={"status": "baja"}).status_code == 422
    assert requests.patch(f"{base_url}/fleet/drivers/{conductor['id']}", headers=auth_headers, json={"assigned_vehicle_id": str(uuid.uuid4())}).status_code == 422
    assert requests.patch(f"{base_url}/fleet/vehicles/{vehiculo['id']}", headers=auth_headers, json={"status": "vendido"}).status_code == 422
    assert requests.patch(f"{base_url}/fleet/vehicles/{vehiculo['id']}", headers=auth_headers, json={"current_mileage_km": -1}).status_code == 422
    vehiculo_nuevo = {"plate": "VAL-0001", "brand": "P", "model": "P", "year": 2024, "status": "vendido"}
    assert requests.post(f"{base_url}/fleet/vehicles", headers=auth_headers, json=vehiculo_nuevo).status_code == 422

    despues_c = requests.get(f"{base_url}/fleet/drivers/{conductor['id']}", headers=auth_headers).json()
    despues_v = requests.get(f"{base_url}/fleet/vehicles/{vehiculo['id']}", headers=auth_headers).json()
    assert (despues_c["license_type"], despues_c["status"], despues_v["status"]) == antes, "los rechazos no deben cambiar nada"

    ok = requests.post(f"{base_url}/fleet/drivers", headers=auth_headers, json={**nuevo, "license_type": "Tipo E1"})
    assert ok.status_code == 201 and ok.json()["license_type"] == "E"


# ------------------------------------------------------------------ RNF-11: rectificar y suprimir
def test_rectificar_la_licencia_y_suprimir_los_datos_personales(base_url, auth_headers, datos):
    vehiculo = datos["vehiculos"][0]
    sufijo = uuid.uuid4().hex[:8]
    otro = requests.post(f"{base_url}/fleet/drivers", headers=auth_headers, json={"full_name": "Otro Conductor", "license_number": f"OTRO-{sufijo}"}).json()
    r = requests.post(
        f"{base_url}/fleet/drivers",
        headers=auth_headers,
        json={"full_name": "Persona Para Suprimir", "license_number": f"SUP-{sufijo}", "license_type": "E", "phone": "0991112233", "assigned_vehicle_id": vehiculo["id"]},
    )
    assert r.status_code == 201
    conductor = r.json()
    token = conductor["qr_token"]
    url = f"{base_url}/fleet/drivers/{conductor['id']}"

    # rectificación: la licencia es editable, sin duplicar la de otro conductor
    rect = requests.patch(url, headers=auth_headers, json={"license_number": f"SUP-{sufijo}-B"})
    assert rect.status_code == 200 and rect.json()["license_number"] == f"SUP-{sufijo}-B"
    assert requests.patch(url, headers=auth_headers, json={"license_number": otro["license_number"]}).status_code == 409
    assert requests.patch(url, headers=auth_headers, json={"license_number": f"SUP-{sufijo}-B"}).status_code == 200  # la propia no es duplicado

    # con un viaje abierto no se puede suprimir
    viaje = _crear_viaje(base_url, auth_headers, vehiculo, conductor)
    bloqueado = requests.post(f"{url}/anonymize", headers=auth_headers)
    assert bloqueado.status_code == 409 and "viaje" in bloqueado.text
    requests.patch(f"{base_url}/fleet/trips/{viaje['id']}/cancel", headers=auth_headers)

    # supresión: no queda ningún dato personal, la credencial deja de servir y el historial se conserva
    assert requests.get(f"{base_url}/fleet/despacho/{conductor['id']}", headers={"X-Despacho-Token": token}).status_code == 200
    suprimido = requests.post(f"{url}/anonymize", headers=auth_headers)
    assert suprimido.status_code == 200
    d = suprimido.json()
    assert d["full_name"].startswith("Conductor anonimizado") and d["license_number"].startswith("ANON-")
    assert d["phone"] is None and d["license_type"] is None and d["assigned_vehicle_id"] is None
    assert d["status"] == "inactivo" and d["has_qr"] is False and d["anonymized_at"]
    assert "Persona Para Suprimir" not in requests.get(f"{base_url}/fleet/drivers", headers=auth_headers).text
    assert requests.get(f"{base_url}/fleet/despacho/{conductor['id']}", headers={"X-Despacho-Token": token}).status_code == 401
    assert requests.get(f"{base_url}/fleet/trips/{viaje['id']}", headers=auth_headers).json()["driver_id"] == conductor["id"]

    # es irreversible
    assert requests.patch(url, headers=auth_headers, json={"full_name": "Otra vez"}).status_code == 409
    assert requests.post(f"{url}/regenerate-qr", headers=auth_headers).status_code == 409
    assert requests.post(f"{url}/anonymize", headers=auth_headers).status_code == 409


# ------------------------------------------------------------------ RF-07: el odómetro no retrocede
def test_cerrar_un_viaje_no_hace_retroceder_el_odometro_del_vehiculo(base_url, auth_headers, datos):
    vehiculo = next(v for v in _get(base_url, auth_headers, "/fleet/vehicles") if v["status"] == "activo")
    conductor = datos["conductores"][0]
    base_km = vehiculo["current_mileage_km"]
    ahora = datetime.now(timezone.utc)

    def cerrar(km_inicial, km_final, horas):
        viaje = _crear_viaje(base_url, auth_headers, vehiculo, conductor, salida=ahora + timedelta(hours=horas), km=km_inicial)
        assert requests.patch(f"{base_url}/fleet/trips/{viaje['id']}/start", headers=auth_headers).status_code == 200
        r = requests.patch(
            f"{base_url}/fleet/trips/{viaje['id']}/close", headers=auth_headers,
            json={"end_mileage_km": km_final, "arrival_at": (ahora + timedelta(hours=horas + 2)).isoformat()},
        )
        assert r.status_code == 200, r.text

    def odometro():
        return requests.get(f"{base_url}/fleet/vehicles/{vehiculo['id']}", headers=auth_headers).json()["current_mileage_km"]

    cerrar(base_km, base_km + 500, 1)
    assert odometro() == base_km + 500
    cerrar(base_km, base_km + 200, 2)  # cierre fuera de orden con un final menor al ya registrado
    assert odometro() == base_km + 500, "el odómetro no debe retroceder"
