"""Regresión del N+1 (Fase 5): las consultas del tablero que leen mantenimientos deben pedirlos a
fleet-core en UNA sola llamada, sin importar cuántos vehículos tenga la flota. Antes cada una hacía
una llamada HTTP por vehículo (12 con la flota piloto) y bajo carga eran las más lentas.

Se usa un cliente simulado con 12 vehículos y dos mantenimientos por vehículo, con números calculados
a mano, para comprobar a la vez que el resultado es el esperado y que la cantidad de llamadas es 1."""
import uuid
from datetime import date
from decimal import Decimal

from app.core.fleet_client import FleetClient
from app.dashboards import service

D = Decimal
N = 12  # vehículos
VEHICULOS = [
    {"id": str(uuid.UUID(int=i)), "plate": f"TST-{i:04d}", "brand": "M", "model": "X", "current_mileage_km": 10_000 * i}
    for i in range(1, N + 1)
]

# ESCENARIO: cada vehículo i (1..12) tiene
#   - un cambio de aceite COMPLETADO el 2026-09-05 con costo 100 + i        (total: 12·100 + (1+…+12) = 1 278,00)
#   - un cambio de llantas PENDIENTE: vencido si i es impar (-50 km), próximo si es par (400 km)
COSTO_TOTAL = D("1278.00")


def _registros():
    registros = []
    for i, v in enumerate(VEHICULOS, start=1):
        registros.append({
            "id": str(uuid.uuid4()), "vehicle_id": v["id"], "maintenance_type": "aceite", "category": "preventivo",
            "scheduled_mileage_km": None, "performed_mileage_km": 1000 + i, "cost": f"{100 + i}.00",
            "performed_at": "2026-09-05", "status": "completado", "created_at": "2026-09-05T10:00:00+00:00",
            "km_remaining": None, "urgency": None,
        })
        vencido = i % 2 == 1
        registros.append({
            "id": str(uuid.uuid4()), "vehicle_id": v["id"], "maintenance_type": "llantas", "category": "correctivo",
            "scheduled_mileage_km": v["current_mileage_km"] + (-50 if vencido else 400), "performed_mileage_km": None,
            "cost": None, "performed_at": None, "status": "pendiente", "created_at": "2026-09-06T10:00:00+00:00",
            "km_remaining": -50 if vencido else 400, "urgency": "vencido" if vencido else "proximo",
        })
    return registros


class FlotaQueCuenta:
    """Cliente de fleet-core simulado: registra cada llamada y aplica los mismos filtros que el real."""

    def __init__(self):
        self.calls = []
        self._registros = _registros()

    def list_vehicles(self):
        self.calls.append(("list_vehicles",))
        return list(VEHICULOS)

    def list_maintenance_records(self, vehicle_id=None, status_filter=None):
        self.calls.append(("list_maintenance_records", vehicle_id, status_filter))
        return [r for r in self._registros
                if (vehicle_id is None or r["vehicle_id"] == vehicle_id) and (status_filter is None or r["status"] == status_filter)]

    def maintenance_policy(self):
        self.calls.append(("maintenance_policy",))
        return {"version": "t", "estado": "t", "procedencia": "t", "proximo_km": 1500, "proximo_km_por_tipo": {}}

    def maintenance_aggregate(self, *_):
        self.calls.append(("maintenance_aggregate",))
        return []

    def llamadas_de_mantenimiento(self):
        return [c for c in self.calls if c[0] == "list_maintenance_records"]


def test_el_cliente_ya_no_ofrece_el_historial_por_vehiculo():
    """Reintroducir list_maintenance(vehicle_id) invitaría a volver a un bucle de una llamada por vehículo."""
    assert not hasattr(FleetClient, "list_maintenance")
    assert hasattr(FleetClient, "list_maintenance_records")


def test_el_reporte_de_mantenimientos_pide_todo_en_una_llamada():
    fleet = FlotaQueCuenta()
    items = service.build_maintenance_report(fleet)
    assert fleet.llamadas_de_mantenimiento() == [("list_maintenance_records", None, None)]
    assert len(items) == 2 * N
    assert sum(1 for x in items if x.status == "completado") == N
    assert sum((x.cost for x in items if x.cost), D("0")) == COSTO_TOTAL


def test_el_reporte_de_un_vehiculo_sigue_siendo_una_llamada_filtrada():
    fleet = FlotaQueCuenta()
    un_vehiculo = VEHICULOS[2]
    items = service.build_maintenance_report(fleet, vehicle_id=un_vehiculo["id"])
    assert fleet.llamadas_de_mantenimiento() == [("list_maintenance_records", un_vehiculo["id"], None)]
    assert [x.vehicle_plate for x in items] == [un_vehiculo["plate"]] * 2


def test_el_reporte_respeta_el_periodo_con_una_sola_llamada():
    fleet = FlotaQueCuenta()
    # el completado es del 5 de septiembre y el pendiente se creó el 6: solo el primero cae en 1–5 de septiembre
    items = service.build_maintenance_report(fleet, date_from=date(2026, 9, 1), date_to=date(2026, 9, 5))
    assert len(fleet.llamadas_de_mantenimiento()) == 1
    assert len(items) == N and all(x.status == "completado" for x in items)


def test_el_reporte_sin_iva_convierte_cada_costo_una_vez():
    fleet = FlotaQueCuenta()
    items = service.build_maintenance_report(fleet, iva_mode="neto")
    primero = next(x for x in items if x.vehicle_plate == VEHICULOS[0]["plate"] and x.status == "completado")
    assert primero.cost == D("87.83")  # 101,00 / 1,15
    assert len(fleet.llamadas_de_mantenimiento()) == 1


def test_el_estado_de_mantenimiento_pide_todo_en_una_llamada():
    fleet = FlotaQueCuenta()
    estado = service.build_maintenance_status(fleet)
    assert fleet.llamadas_de_mantenimiento() == [("list_maintenance_records", None, None)]
    assert len(estado.alerts) == N
    assert [a.urgency for a in estado.alerts] == ["vencido"] * (N // 2) + ["proximo"] * (N // 2)  # los vencidos primero
    assert [(m.category, m.count, m.total_cost) for m in estado.mix] == [("preventivo", N, COSTO_TOTAL)]


def test_la_prioridad_ahp_pide_solo_los_pendientes_y_en_una_llamada():
    fleet = FlotaQueCuenta()
    respuesta = service.build_maintenance_priority(fleet)
    assert fleet.llamadas_de_mantenimiento() == [("list_maintenance_records", None, "pendiente")]
    assert len(respuesta.items) == N
    # el más urgente (vencido) va antes que el próximo a vencer, con todo lo demás igual
    assert respuesta.items[0].urgency == "vencido"


def test_los_gastos_del_tablero_piden_los_mantenimientos_completados_en_una_llamada():
    class Flota(FlotaQueCuenta):
        def expense_aggregate(self, *_): return []
        def trip_aggregate(self, *_): return []

    fleet = Flota()
    registros = service.build_expense_records(fleet, category="mantenimiento")
    assert fleet.llamadas_de_mantenimiento() == [("list_maintenance_records", None, "completado")]
    assert len(registros) == N
    assert sum((r.amount for r in registros), D("0")) == COSTO_TOTAL
