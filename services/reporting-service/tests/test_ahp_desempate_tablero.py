"""El tablero de prioridad (RF-19/RF-20) desempata por kilometraje: a igual puntaje AHP aparece primero el
mantenimiento más vencido. Los expertos calificaron igual de críticos los tipos de mantenimiento y los
propietarios entrevistados deciden «por seguridad primero y luego por el kilómetro»; sin este desempate el
orden de los empatados dependía del orden en que fleet-core devolvía los registros."""
import uuid

from app.dashboards import service

VEHICULOS = [{"id": str(uuid.UUID(int=i)), "plate": f"TST-{i}", "brand": "M", "model": "X", "current_mileage_km": 50_000} for i in (1, 2, 3)]
# Mismo tipo y los tres vencidos (urgencia 1,0): mismo puntaje. fleet-core los devuelve del menos al más vencido.
KM = dict(zip((v["id"] for v in VEHICULOS), (-50, None, -900)))


class Flota:
    def list_vehicles(self):
        return list(VEHICULOS)

    def list_maintenance_records(self, vehicle_id=None, status_filter=None):
        return [{"id": str(uuid.uuid4()), "vehicle_id": v["id"], "maintenance_type": "frenos", "category": "preventivo",
                 "status": "pendiente", "cost": None, "km_remaining": KM[v["id"]],
                 "urgency": "vencido" if KM[v["id"]] is not None else None}
                for v in VEHICULOS if vehicle_id in (None, v["id"])]

    def maintenance_policy(self):
        return {"version": "t", "estado": "t", "procedencia": "t", "proximo_km": 1000, "proximo_km_por_tipo": {}}

    def maintenance_aggregate(self, *_):
        return []


def test_a_igual_puntaje_el_tablero_muestra_primero_el_mas_vencido():
    items = service.build_maintenance_priority(Flota()).items
    con_km = [i for i in items if i.km_remaining is not None]
    assert [i.vehicle_plate for i in con_km] == ["TST-3", "TST-1"]
    assert con_km[0].priority_score == con_km[1].priority_score
    assert items[-1].km_remaining is None  # sin kilometraje programado: urgencia menor, va al final
