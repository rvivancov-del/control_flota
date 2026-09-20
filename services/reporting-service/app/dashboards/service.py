"""Construye todas las respuestas del dashboard (RF-15 a RF-20) agregando en
memoria las filas ya sumadas por SQL que entrega fleet-core-service -- este
módulo no toca la base de datos ni conoce SQL, solo combina lo que
FleetClient trae por HTTP."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.fleet_client import FleetClient
from app.dashboards import ahp
from app.dashboards.schemas import (
    AhpCriteriaWeights,
    DashboardSummary,
    DriverExpenseBreakdown,
    DriverSummary,
    DriverSummaryResponse,
    ExpenseBreakdown,
    ExpenseRecord,
    MaintenanceAlertDetail,
    MaintenanceMixEntry,
    MaintenancePriorityItem,
    MaintenancePriorityResponse,
    MaintenanceReportItem,
    MaintenanceStatus,
    RouteSummary,
    RouteSummaryResponse,
    TrendPoint,
    TrendResponse,
    VehicleSummary,
)

_EXPENSE_FIELD = {
    "combustible": "combustible",
    "peaje": "peaje",
    "alimentacion": "alimentacion",
}

VALID_CATEGORIES = {"combustible", "peaje", "alimentacion", "mantenimiento"}

# A partir de cuántos km restantes un mantenimiento pendiente pasa de
# "normal" a "próximo" — umbral de alerta temprana, no solo "ya vencido".
URGENCY_THRESHOLD_KM = 1500


def _date_in_range(value: date, date_from: Optional[date], date_to: Optional[date]) -> bool:
    """True si value cae dentro de [date_from, date_to] (límites abiertos si son None)."""
    if date_from and value < date_from:
        return False
    if date_to and value > date_to:
        return False
    return True


def _parse_iso_date(value: str) -> date:
    """Convierte un timestamp ISO (con o sin 'Z') devuelto por fleet-core-service en date."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _maintenance_reference_date(record: dict) -> Optional[date]:
    """Una fecha de mantenimiento pendiente usa created_at; una completada, performed_at."""
    raw = record.get("performed_at") or record.get("created_at")
    if not raw:
        return None
    return _parse_iso_date(raw) if "T" in raw else date.fromisoformat(raw[:10])


def build_dashboard_summary(
    client: FleetClient,
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
) -> DashboardSummary:
    """RF-15 + RF-16: agrega, por vehículo, el costo total y su composición
    (combustible, peajes, alimentación, mantenimiento) dentro del período dado.

    Toda la suma ocurre en SQL dentro de fleet-core-service (endpoints
    /analytics/*) — este servicio hace 5 llamadas en total sin importar
    cuántos viajes o gastos haya en el período (antes: una llamada HTTP por
    cada viaje, lo que con un año de historia tardaba más de 10 segundos).

    `category` (opcional) acota el costo total mostrado (KPI y columna "Total")
    a un solo tipo de gasto — el desglose completo se calcula siempre, así el
    tablero sigue mostrando los 4 parámetros aunque el total esté filtrado."""
    category = category if category in VALID_CATEGORIES else None
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]
    vehicle_ids = {v["id"] for v in vehicles}

    alerts_by_vehicle: dict[str, int] = {}
    for alert in client.list_maintenance_alerts():
        alerts_by_vehicle[alert["vehicle_id"]] = alerts_by_vehicle.get(alert["vehicle_id"], 0) + 1

    breakdown_by_vehicle: dict[str, ExpenseBreakdown] = defaultdict(ExpenseBreakdown)
    for row in client.expense_aggregate(date_from, date_to):
        vid = row["vehicle_id"]
        if vid not in vehicle_ids:
            continue
        field = _EXPENSE_FIELD.get(row["type"])
        if field is not None:
            b = breakdown_by_vehicle[vid]
            setattr(b, field, getattr(b, field) + Decimal(str(row["amount_total"])))

    for row in client.maintenance_aggregate(date_from, date_to):
        vid = row["vehicle_id"]
        if vid not in vehicle_ids:
            continue
        breakdown_by_vehicle[vid].mantenimiento += Decimal(str(row["cost_total"]))

    trips_by_vehicle: dict[str, int] = defaultdict(int)
    distance_by_vehicle: dict[str, int] = defaultdict(int)
    revenue_by_vehicle: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    active_days_by_vehicle: dict[str, set] = defaultdict(set)
    for row in client.trip_aggregate(date_from, date_to):
        vid = row["vehicle_id"]
        if vid not in vehicle_ids:
            continue
        trips_by_vehicle[vid] += row["trip_count"]
        distance_by_vehicle[vid] += row["distance_km"]
        revenue_by_vehicle[vid] += Decimal(str(row["revenue_total"]))
        active_days_by_vehicle[vid].add(row["trip_date"])

    fuel_liters_by_vehicle: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in client.expense_aggregate(date_from, date_to):
        vid = row["vehicle_id"]
        if vid not in vehicle_ids or row["type"] != "combustible":
            continue
        fuel_liters_by_vehicle[vid] += Decimal(str(row["liters_total"]))

    period_days = (date_to - date_from).days + 1 if date_from and date_to else None

    summaries: list[VehicleSummary] = []
    fleet_total = Decimal("0")
    fleet_revenue = Decimal("0")
    any_revenue = False

    for vehicle in vehicles:
        vid = vehicle["id"]
        breakdown = breakdown_by_vehicle.get(vid, ExpenseBreakdown())
        total_cost = (
            getattr(breakdown, category)
            if category
            else breakdown.combustible + breakdown.peaje + breakdown.alimentacion + breakdown.mantenimiento
        )
        fleet_total += total_cost

        revenue = revenue_by_vehicle.get(vid, Decimal("0"))
        has_revenue = revenue > 0
        if has_revenue:
            any_revenue = True
            fleet_revenue += revenue
        margin = (revenue - total_cost) if has_revenue else None

        distance = distance_by_vehicle.get(vid, 0)
        fuel_liters = fuel_liters_by_vehicle.get(vid, Decimal("0"))
        fuel_efficiency = (fuel_liters / distance * 100) if distance > 0 and fuel_liters > 0 else None

        active_days = len(active_days_by_vehicle.get(vid, set()))
        utilization_pct = (
            Decimal(active_days) / Decimal(period_days) * 100 if period_days and period_days > 0 else None
        )

        summaries.append(
            VehicleSummary(
                vehicle_id=vid,
                plate=vehicle["plate"],
                brand=vehicle["brand"],
                model=vehicle["model"],
                current_mileage_km=vehicle["current_mileage_km"],
                trip_count=trips_by_vehicle.get(vid, 0),
                distance_km=distance,
                total_cost=total_cost,
                breakdown=breakdown,
                pending_maintenance_alerts=alerts_by_vehicle.get(vid, 0),
                revenue=revenue if has_revenue else None,
                margin=margin,
                fuel_liters=fuel_liters,
                fuel_efficiency_l_100km=fuel_efficiency,
                active_days=active_days if period_days else None,
                period_days=period_days,
                utilization_pct=utilization_pct,
            )
        )

    return DashboardSummary(
        vehicles=summaries,
        fleet_total_cost=fleet_total,
        fleet_total_revenue=fleet_revenue if any_revenue else None,
        fleet_total_margin=(fleet_revenue - fleet_total) if any_revenue else None,
    )


def build_route_summary(
    client: FleetClient,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> RouteSummaryResponse:
    """Costo y distancia por ruta — el contexto de dificultad que falta para
    leer con justicia el ranking de costo/km por conductor: un número alto
    puede ser mala conducción, o puede ser que le tocaron las rutas caras."""
    routes: list[RouteSummary] = []
    for row in client.route_aggregate(date_from, date_to):
        distance = row["avg_distance_km"]
        cost = Decimal(str(row["cost_total"]))
        cost_per_km = (cost / row["trip_count"] / distance) if distance > 0 and row["trip_count"] > 0 else None
        routes.append(
            RouteSummary(
                origin=row["origin"],
                destination=row["destination"],
                trip_count=row["trip_count"],
                avg_distance_km=distance,
                cost_total=cost,
                cost_per_km=cost_per_km,
            )
        )
    routes.sort(key=lambda r: r.cost_per_km or Decimal("0"), reverse=True)
    return RouteSummaryResponse(routes=routes)


def build_driver_summary(
    client: FleetClient,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
) -> DriverSummaryResponse:
    """Mismo análisis que build_dashboard_summary pero por conductor en vez de
    por vehículo — responde "¿quién genera más gasto operativo, y qué tan
    eficiente es por kilómetro conducido?". Sin mantenimiento: el
    mantenimiento es del vehículo, no depende de quién lo conducía."""
    category = category if category in VALID_CATEGORIES and category != "mantenimiento" else None
    drivers = client.list_drivers()
    driver_ids = {d["id"] for d in drivers}

    breakdown_by_driver: dict[str, DriverExpenseBreakdown] = defaultdict(DriverExpenseBreakdown)
    for row in client.expense_aggregate(date_from, date_to):
        did = row["driver_id"]
        if did not in driver_ids:
            continue
        field = _EXPENSE_FIELD.get(row["type"])
        if field is not None:
            b = breakdown_by_driver[did]
            setattr(b, field, getattr(b, field) + Decimal(str(row["amount_total"])))

    trips_by_driver: dict[str, int] = defaultdict(int)
    distance_by_driver: dict[str, int] = defaultdict(int)
    revenue_by_driver: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in client.trip_aggregate(date_from, date_to):
        did = row["driver_id"]
        if did not in driver_ids:
            continue
        trips_by_driver[did] += row["trip_count"]
        distance_by_driver[did] += row["distance_km"]
        revenue_by_driver[did] += Decimal(str(row["revenue_total"]))

    fuel_liters_by_driver: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in client.expense_aggregate(date_from, date_to):
        did = row["driver_id"]
        if did not in driver_ids or row["type"] != "combustible":
            continue
        fuel_liters_by_driver[did] += Decimal(str(row["liters_total"]))

    summaries: list[DriverSummary] = []
    fleet_total = Decimal("0")

    for driver in drivers:
        did = driver["id"]
        breakdown = breakdown_by_driver.get(did, DriverExpenseBreakdown())
        total_cost = getattr(breakdown, category) if category else (
            breakdown.combustible + breakdown.peaje + breakdown.alimentacion
        )
        distance = distance_by_driver.get(did, 0)
        cost_per_km = (total_cost / distance) if distance > 0 else None
        fleet_total += total_cost

        revenue = revenue_by_driver.get(did, Decimal("0"))
        has_revenue = revenue > 0
        margin = (revenue - total_cost) if has_revenue else None

        fuel_liters = fuel_liters_by_driver.get(did, Decimal("0"))
        fuel_efficiency = (fuel_liters / distance * 100) if distance > 0 and fuel_liters > 0 else None

        summaries.append(
            DriverSummary(
                driver_id=did,
                full_name=driver["full_name"],
                trip_count=trips_by_driver.get(did, 0),
                distance_km=distance,
                total_cost=total_cost,
                cost_per_km=cost_per_km,
                breakdown=breakdown,
                revenue=revenue if has_revenue else None,
                margin=margin,
                fuel_liters=fuel_liters,
                fuel_efficiency_l_100km=fuel_efficiency,
            )
        )

    return DriverSummaryResponse(drivers=summaries, fleet_total_cost=fleet_total)


def _period_bucket(value: date, period: str) -> tuple[str, date]:
    """Agrupa una fecha en su semana, mes o año — mismo patrón que el reporte
    de 'costos en el tiempo' de Odoo Fleet, adaptado a agregación en memoria."""
    if period == "week":
        start = value - timedelta(days=value.weekday())
        label = f"Sem {start.isocalendar()[1]} ({start.strftime('%d/%m')})"
        return label, start
    if period == "year":
        start = value.replace(month=1, day=1)
        return str(start.year), start
    start = value.replace(day=1)
    return start.strftime("%b %Y"), start


def build_cost_trend(
    client: FleetClient,
    period: str = "month",
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
) -> TrendResponse:
    """RF-16: costo total por período (semana, mes o año) — la vista de
    tendencia que un ERP de flota (p. ej. Odoo Fleet) reporta junto al total
    acumulado, en vez de un solo número estático.

    `category` (opcional) acota `total_cost` de cada punto al tipo de gasto
    seleccionado en el tablero, igual que en build_dashboard_summary."""
    category = category if category in VALID_CATEGORIES else None
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]
    vehicle_ids = {v["id"] for v in vehicles}

    buckets: dict[str, ExpenseBreakdown] = defaultdict(ExpenseBreakdown)
    bucket_start: dict[str, date] = {}

    for row in client.expense_aggregate(date_from, date_to):
        if row["vehicle_id"] not in vehicle_ids:
            continue
        field = _EXPENSE_FIELD.get(row["type"])
        if field is None:
            continue
        label, start = _period_bucket(date.fromisoformat(row["expense_date"]), period)
        bucket_start.setdefault(label, start)
        b = buckets[label]
        setattr(b, field, getattr(b, field) + Decimal(str(row["amount_total"])))

    for row in client.maintenance_aggregate(date_from, date_to):
        if row["vehicle_id"] not in vehicle_ids:
            continue
        label, start = _period_bucket(date.fromisoformat(row["performed_at"]), period)
        bucket_start.setdefault(label, start)
        buckets[label].mantenimiento += Decimal(str(row["cost_total"]))

    points = [
        TrendPoint(
            period_label=label,
            total_cost=(
                getattr(b, category)
                if category
                else b.combustible + b.peaje + b.alimentacion + b.mantenimiento
            ),
            breakdown=b,
        )
        for label, b in sorted(buckets.items(), key=lambda kv: bucket_start[kv[0]])
    ]
    return TrendResponse(points=points)


def build_expense_records(
    client: FleetClient,
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
) -> list[ExpenseRecord]:
    """Insumo del histograma y la dispersión costo-vs-kilometraje del
    tablero. Los gastos de viaje (combustible/peaje/alimentación) vienen
    agregados por día desde SQL — a la escala de una flota real, "un punto
    por día" sigue mostrando la forma real de la distribución y los valores
    atípicos, sin repetir el problema de una llamada HTTP por recibo. El
    mantenimiento sigue viniendo registro por registro (ya es barato: una
    llamada por vehículo, no por evento)."""
    category = category if category in VALID_CATEGORIES else None
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]
    vehicle_ids = {v["id"] for v in vehicles}
    plate_by_id = {v["id"]: v["plate"] for v in vehicles}

    records: list[ExpenseRecord] = []

    if category is None or category in _EXPENSE_FIELD:
        mileage_by_key: dict[tuple[str, str], int] = {}
        for row in client.trip_aggregate(date_from, date_to):
            if row["vehicle_id"] not in vehicle_ids:
                continue
            mileage_by_key[(row["vehicle_id"], row["trip_date"])] = row["end_mileage_km"]

        for row in client.expense_aggregate(date_from, date_to):
            vid = row["vehicle_id"]
            if vid not in vehicle_ids:
                continue
            if category and row["type"] != category:
                continue
            if row["type"] not in _EXPENSE_FIELD:
                continue
            records.append(
                ExpenseRecord(
                    vehicle_plate=plate_by_id[vid],
                    category=row["type"],
                    amount=Decimal(str(row["amount_total"])),
                    mileage_km=mileage_by_key.get((vid, row["expense_date"])),
                    occurred_at=row["expense_date"],
                )
            )

    if category is None or category == "mantenimiento":
        for vehicle in vehicles:
            for record in client.list_maintenance(vehicle["id"]):
                if record["status"] != "completado" or not record.get("cost"):
                    continue
                ref_date = _maintenance_reference_date(record)
                if ref_date is not None and not _date_in_range(ref_date, date_from, date_to):
                    continue
                mileage = record.get("performed_mileage_km") or record.get("scheduled_mileage_km")
                records.append(
                    ExpenseRecord(
                        vehicle_plate=vehicle["plate"],
                        category="mantenimiento",
                        amount=Decimal(str(record["cost"])),
                        mileage_km=mileage,
                        occurred_at=record.get("performed_at") or record.get("created_at"),
                    )
                )

    return records


def build_maintenance_report(
    client: FleetClient,
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[MaintenanceReportItem]:
    """RF-17: mantenimientos (pendientes y completados) dentro del período,
    con su costo — el detalle que el resumen de costos no desglosa registro
    por registro."""
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]

    items: list[MaintenanceReportItem] = []
    for vehicle in vehicles:
        for record in client.list_maintenance(vehicle["id"]):
            ref_date = _maintenance_reference_date(record)
            if ref_date is not None and not _date_in_range(ref_date, date_from, date_to):
                continue
            items.append(
                MaintenanceReportItem(
                    vehicle_plate=vehicle["plate"],
                    maintenance_type=record["maintenance_type"],
                    category=record["category"],
                    status=record["status"],
                    scheduled_mileage_km=record.get("scheduled_mileage_km"),
                    performed_mileage_km=record.get("performed_mileage_km"),
                    cost=record.get("cost"),
                    performed_at=record.get("performed_at"),
                )
            )
    return items


def build_maintenance_status(client: FleetClient, vehicle_id: Optional[str] = None) -> MaintenanceStatus:
    """Bloque de 'acción requerida' del tablero: qué mantenimientos pendientes
    son urgentes (por kilometraje restante) y si la flota se mantiene de
    forma preventiva o a la fuerza (correctivo) — no acota por fecha, porque
    la urgencia se mide contra el kilometraje actual del vehículo, no contra
    un período de tiempo."""
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]

    alerts: list[MaintenanceAlertDetail] = []
    mix_by_category: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_cost": Decimal("0")})

    for vehicle in vehicles:
        current_km = vehicle["current_mileage_km"]
        for record in client.list_maintenance(vehicle["id"]):
            if record["status"] == "completado":
                if record.get("cost"):
                    entry = mix_by_category[record["category"]]
                    entry["count"] += 1
                    entry["total_cost"] += Decimal(str(record["cost"]))
                continue
            if record["status"] != "pendiente":
                continue

            scheduled = record.get("scheduled_mileage_km")
            remaining = (scheduled - current_km) if scheduled is not None else None
            if remaining is None:
                urgency = "normal"
            elif remaining <= 0:
                urgency = "vencido"
            elif remaining <= URGENCY_THRESHOLD_KM:
                urgency = "proximo"
            else:
                urgency = "normal"

            alerts.append(
                MaintenanceAlertDetail(
                    vehicle_id=vehicle["id"],
                    vehicle_plate=vehicle["plate"],
                    maintenance_type=record["maintenance_type"],
                    category=record["category"],
                    scheduled_mileage_km=scheduled,
                    current_mileage_km=current_km,
                    km_remaining=remaining,
                    urgency=urgency,
                )
            )

    urgency_rank = {"vencido": 0, "proximo": 1, "normal": 2}
    alerts.sort(key=lambda a: (urgency_rank[a.urgency], a.km_remaining if a.km_remaining is not None else 10**9))

    mix = [
        MaintenanceMixEntry(category=category, count=v["count"], total_cost=v["total_cost"])
        for category, v in mix_by_category.items()
    ]
    return MaintenanceStatus(alerts=alerts, mix=mix)


def build_maintenance_priority(
    client: FleetClient, vehicle_id: Optional[str] = None
) -> MaintenancePriorityResponse:
    """RF-20: ranking de mantenimientos pendientes por Analytic Hierarchy
    Process (Saaty, 1980) sobre tres criterios — seguridad, urgencia por
    kilometraje y costo estimado — en vez del criterio único (solo km
    restantes) de `build_maintenance_status`.

    Ver app/dashboards/ahp.py para la matriz de comparación pareada, la
    justificación de los pesos y el cálculo del ratio de consistencia.
    Metodológicamente equivalente a lo revisado en Akcaer, Öztürk y Yüksel
    (2026) y Nugraha, Muhidong y Soma (2025), adaptado de mantenimiento de
    infraestructura vial/ferroviaria a mantenimiento de flota vehicular."""
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]
    plate_by_id = {v["id"]: v["plate"] for v in vehicles}
    current_km_by_id = {v["id"]: v["current_mileage_km"] for v in vehicles}

    # Costo historico promedio por tipo de mantenimiento, agregado sobre
    # TODA la flota (no solo el vehiculo en cuestion) para tener una muestra
    # razonable incluso con una flota piloto pequena.
    cost_sum_by_type: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    cost_count_by_type: dict[str, int] = defaultdict(int)
    for row in client.maintenance_aggregate():
        cost_sum_by_type[row["maintenance_type"]] += Decimal(str(row["cost_total"]))
        cost_count_by_type[row["maintenance_type"]] += row["count"]
    avg_cost_by_type = {
        mtype: float(cost_sum_by_type[mtype] / cost_count_by_type[mtype])
        for mtype in cost_sum_by_type
        if cost_count_by_type[mtype] > 0
    }

    items: list[MaintenancePriorityItem] = []
    for vehicle in vehicles:
        vid = vehicle["id"]
        current_km = current_km_by_id[vid]
        for record in client.list_maintenance(vid):
            if record["status"] != "pendiente":
                continue
            scheduled = record.get("scheduled_mileage_km")
            km_remaining = (scheduled - current_km) if scheduled is not None else None

            mtype = record["maintenance_type"]
            seguridad = ahp.SAFETY_CRITICALITY.get(mtype, ahp.SAFETY_CRITICALITY["otro"])
            urgencia = ahp.urgency_score(km_remaining, URGENCY_THRESHOLD_KM)
            costo = ahp.cost_score(mtype, avg_cost_by_type)
            score = ahp.priority_score(seguridad, urgencia, costo)

            items.append(
                MaintenancePriorityItem(
                    vehicle_id=vid,
                    vehicle_plate=plate_by_id[vid],
                    maintenance_type=mtype,
                    category=record["category"],
                    km_remaining=km_remaining,
                    seguridad_score=round(seguridad, 4),
                    urgencia_score=round(urgencia, 4),
                    costo_score=round(costo, 4),
                    priority_score=round(score, 4),
                )
            )

    items.sort(key=lambda item: item.priority_score, reverse=True)
    weights = ahp.AHP_WEIGHTS
    return MaintenancePriorityResponse(
        items=items,
        weights=AhpCriteriaWeights(
            seguridad=round(weights.seguridad, 4),
            urgencia=round(weights.urgencia, 4),
            costo=round(weights.costo, 4),
            consistency_ratio=round(weights.consistency_ratio, 4),
            is_consistent=weights.is_consistent,
        ),
    )
