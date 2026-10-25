"""Construye todas las respuestas del dashboard (RF-15 a RF-20) agregando en
memoria las filas ya sumadas por SQL que entrega fleet-core-service -- este
módulo no toca la base de datos ni conoce SQL, solo combina lo que
FleetClient trae por HTTP."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.fleet_client import FleetClient
from app.dashboards import ahp, alert_policy, cost_model, iva_config
from app.dashboards.schemas import (
    AhpConfigInfo,
    AhpCriteriaWeights,
    CostCategoryLine,
    CostStructure,
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
    VehicleAttentionItem,
    VehicleAttentionResponse,
    VehicleAttentionWeights,
    VehicleSummary,
)

_EXPENSE_FIELD = {
    "combustible": "combustible",
    "peaje": "peaje",
    "alimentacion": "alimentacion",
}

VALID_CATEGORIES = {"combustible", "peaje", "alimentacion", "mantenimiento"}

ZERO = Decimal("0")
_q2 = cost_model.q2


def _iva_mode(iva_mode: Optional[str]) -> str:
    """Modo de IVA pedido, o el predeterminado de iva_config.json ('bruto')."""
    mode = iva_mode or iva_config.CONFIG.default_mode
    if mode not in iva_config.MODES:
        raise ValueError(f"iva_mode debe ser uno de {iva_config.MODES}, se recibió {mode!r}")
    return mode


def _convert(item: str, amount: Decimal, mode: str) -> Decimal:
    """Monto de un rubro en el modo de IVA pedido (sin redondear)."""
    return cost_model.apply_iva({item: amount}, iva_config.CONFIG.rates, mode)[item]


def _cost_structure(ind: cost_model.Indicators, mode: str) -> CostStructure:
    """Indicadores de cost_model → esquema de respuesta, con los redondeos de presentación
    (montos a centavos, costos por km a 4 decimales)."""
    q4 = cost_model.q4
    return CostStructure(
        iva_mode=mode,
        fixed_included=ind.fixed_included,
        distance_km=ind.distance_km,
        variable_cost=_q2(ind.variable_cost),
        fixed_cost=_q2(ind.fixed_cost),
        total_cost=_q2(ind.total_cost),
        cv_per_km=q4(ind.cv_per_km),
        cf_per_km=q4(ind.cf_per_km),
        ct_per_km=q4(ind.ct_per_km),
        revenue=_q2(ind.revenue),
        revenue_per_km=q4(ind.revenue_per_km),
        revenue_coverage_pct=_q2(ind.revenue_coverage_pct),
        profit=_q2(ind.profit),
        profit_per_km=q4(ind.profit_per_km),
        margin_pct=_q2(ind.margin_pct),
        contribution_margin=_q2(ind.contribution_margin),
        personnel_cost=_q2(ind.personnel_cost),
        labour_productivity=_q2(ind.labour_productivity),
        return_on_personnel_cost_pct=_q2(ind.return_on_personnel_cost_pct),
        composition=[
            CostCategoryLine(key=c.key, label=c.label, amount=_q2(c.amount), per_km=q4(c.per_km), share_pct=_q2(c.share_pct))
            for c in ind.composition
        ],
    )


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
    iva_mode: Optional[str] = None,
    include_fixed: bool = False,
) -> DashboardSummary:
    """RF-15 + RF-16 + modelo de costos completo.

    Por vehículo y para la flota entrega el gasto operativo (costos variables), su composición y, en
    `costs` / `fleet_costs`, el modelo completo: Ct = Cv + Cf, costos, ingreso y utilidad por km,
    margen, LP, ROP y la estructura en ocho categorías (ver cost_model.py).

    Toda la suma ocurre en SQL dentro de fleet-core-service (endpoints /analytics/*): pocas llamadas
    sin importar cuántos viajes o gastos haya en el período.

    - `category` acota solo `total_cost` (KPI y columna "Total"); el desglose y los indicadores
      (margen, utilidad) NO cambian con el filtro: el margen siempre se calcula contra el costo completo.
    - `include_fixed` (solo el rol admin) suma los costos fijos por vehículo y el personal, este último
      repartido entre vehículos según los km de cada conductor. Requiere `date_from` y `date_to`,
      porque los costos fijos se prorratean por días.
    - `iva_mode`: 'bruto' (montos pagados) o 'neto' (sin IVA); ver iva_config.py."""
    mode = _iva_mode(iva_mode)
    rates = iva_config.CONFIG.rates
    category = category if category in VALID_CATEGORIES else None
    all_vehicles = client.list_vehicles()
    vehicles = [v for v in all_vehicles if v["id"] == vehicle_id] if vehicle_id else all_vehicles
    vehicle_ids = {v["id"] for v in vehicles}
    fixed_ok = include_fixed and date_from is not None and date_to is not None

    alerts_by_vehicle: dict[str, int] = {}
    for alert in client.list_maintenance_alerts():
        alerts_by_vehicle[alert["vehicle_id"]] = alerts_by_vehicle.get(alert["vehicle_id"], 0) + 1

    # Montos por vehículo y rubro, tal como se pagaron (con IVA).
    gross: dict[str, dict[str, Decimal]] = defaultdict(lambda: dict.fromkeys(cost_model.VARIABLE_ITEMS, ZERO))
    fuel_liters_by_vehicle: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in client.expense_aggregate(date_from, date_to):
        vid = row["vehicle_id"]
        if vid not in vehicle_ids or row["type"] not in _EXPENSE_FIELD:
            continue
        gross[vid][row["type"]] += Decimal(str(row["amount_total"]))
        if row["type"] == "combustible":
            fuel_liters_by_vehicle[vid] += Decimal(str(row["liters_total"]))
    for row in client.maintenance_aggregate(date_from, date_to):
        if row["vehicle_id"] in vehicle_ids:
            gross[row["vehicle_id"]]["mantenimiento"] += Decimal(str(row["cost_total"]))

    trips_by_vehicle: dict[str, int] = defaultdict(int)
    distance_by_vehicle: dict[str, int] = defaultdict(int)
    revenue_by_vehicle: dict[str, Decimal] = defaultdict(lambda: ZERO)
    revenue_km_by_vehicle: dict[str, int] = defaultdict(int)
    active_days_by_vehicle: dict[str, set] = defaultdict(set)
    # km de cada conductor con cada vehículo (de TODA la flota): base para repartir el personal.
    km_by_driver_vehicle: dict[tuple[str, str], int] = defaultdict(int)
    for row in client.trip_aggregate(date_from, date_to):
        vid = row["vehicle_id"]
        km_by_driver_vehicle[(row["driver_id"], vid)] += row["distance_km"]
        if vid not in vehicle_ids:
            continue
        trips_by_vehicle[vid] += row["trip_count"]
        distance_by_vehicle[vid] += row["distance_km"]
        revenue_by_vehicle[vid] += Decimal(str(row["revenue_total"]))
        revenue_km_by_vehicle[vid] += row.get("revenue_distance_km", row["distance_km"])
        active_days_by_vehicle[vid].add(row["trip_date"])

    unallocated = ZERO
    if fixed_ok:
        for row in client.fixed_cost_accrual(date_from, date_to):
            if row["vehicle_id"] in vehicle_ids:
                items = gross[row["vehicle_id"]]
                items[row["category"]] = items.get(row["category"], ZERO) + Decimal(str(row["amount"]))
        personnel_by_driver: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for row in client.personnel_cost_accrual(date_from, date_to):
            personnel_by_driver[row["driver_id"]] += Decimal(str(row["amount"]))
        allocated, unallocated = cost_model.allocate_personnel(dict(personnel_by_driver), dict(km_by_driver_vehicle))
        for vid, amount in allocated.items():
            if vid in vehicle_ids:
                gross[vid]["personal"] = amount
        if vehicle_id:
            unallocated = ZERO  # con un solo vehículo elegido no se muestra lo que no es de ninguno

    period_days = (date_to - date_from).days + 1 if date_from and date_to else None

    summaries: list[VehicleSummary] = []
    net_by_vehicle: dict[str, dict[str, Decimal]] = {}
    fleet_total = ZERO
    fleet_revenue = ZERO
    fleet_revenue_km = 0
    fleet_distance = 0
    any_revenue = False

    for vehicle in vehicles:
        vid = vehicle["id"]
        net = cost_model.apply_iva(gross[vid], rates, mode)
        net_by_vehicle[vid] = net
        breakdown = ExpenseBreakdown(
            combustible=_q2(net["combustible"]),
            peaje=_q2(net["peaje"]),
            alimentacion=_q2(net["alimentacion"]),
            mantenimiento=_q2(net["mantenimiento"]),
        )
        operating_cost = breakdown.combustible + breakdown.peaje + breakdown.alimentacion + breakdown.mantenimiento
        total_cost = getattr(breakdown, category) if category else operating_cost
        fleet_total += total_cost

        revenue = revenue_by_vehicle.get(vid, ZERO)
        has_revenue = revenue > 0
        distance = distance_by_vehicle.get(vid, 0)
        fleet_distance += distance
        if has_revenue:
            any_revenue = True
            fleet_revenue += revenue
            fleet_revenue_km += revenue_km_by_vehicle.get(vid, 0)

        indicators = cost_model.compute_indicators(
            net, distance, revenue if has_revenue else None, revenue_km_by_vehicle.get(vid, 0), include_fixed=fixed_ok
        )
        fuel_liters = fuel_liters_by_vehicle.get(vid, ZERO)
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
                # Margen de contribución: ingreso − costos variables, sin importar el filtro de categoría.
                margin=_q2(indicators.contribution_margin),
                fuel_liters=fuel_liters,
                fuel_efficiency_l_100km=fuel_efficiency,
                active_days=active_days if period_days else None,
                period_days=period_days,
                utilization_pct=utilization_pct,
                costs=_cost_structure(indicators, mode),
            )
        )

    fleet_net = cost_model.sum_items(net_by_vehicle.values())
    if fixed_ok and unallocated > 0:
        fleet_net["personal"] = fleet_net.get("personal", ZERO) + _convert("personal", unallocated, mode)
    fleet_indicators = cost_model.compute_indicators(
        fleet_net, fleet_distance, fleet_revenue if any_revenue else None, fleet_revenue_km, include_fixed=fixed_ok
    )

    return DashboardSummary(
        vehicles=summaries,
        fleet_total_cost=fleet_total,
        fleet_total_revenue=fleet_revenue if any_revenue else None,
        fleet_total_margin=_q2(fleet_indicators.contribution_margin),
        iva_mode=mode,
        fleet_costs=_cost_structure(fleet_indicators, mode),
        fixed_costs_omitted_reason=None if fixed_ok else ("rol" if not include_fixed else "sin_periodo"),
        unallocated_personnel_cost=_q2(_convert("personal", unallocated, mode)) if fixed_ok and not vehicle_id else None,
    )



def build_route_summary(
    client: FleetClient,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    iva_mode: Optional[str] = None,
) -> RouteSummaryResponse:
    """Costo y distancia por ruta — el contexto de dificultad que falta para
    leer con justicia el ranking de costo/km por conductor: un número alto
    puede ser mala conducción, o puede ser que le tocaron las rutas caras."""
    mode = _iva_mode(iva_mode)
    routes: list[RouteSummary] = []
    for row in client.route_aggregate(date_from, date_to):
        distance = row["avg_distance_km"]
        if mode == "bruto":
            cost = Decimal(str(row["cost_total"]))
        else:
            by_type = {item: Decimal(str(row.get(f"cost_{item}", 0))) for item in ("combustible", "peaje", "alimentacion")}
            cost = sum(cost_model.apply_iva(by_type, iva_config.CONFIG.rates, mode).values(), ZERO)
        cost = _q2(cost)
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
    return RouteSummaryResponse(routes=routes, iva_mode=mode)



def build_driver_summary(
    client: FleetClient,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    iva_mode: Optional[str] = None,
    include_fixed: bool = False,
) -> DriverSummaryResponse:
    """Mismo análisis que build_dashboard_summary pero por conductor en vez de
    por vehículo — responde "¿quién genera más gasto operativo, y qué tan
    eficiente es por kilómetro conducido?". Sin mantenimiento: el
    mantenimiento es del vehículo, no depende de quién lo conducía.

    Solo para el admin (`include_fixed`) y con período: el costo de personal del conductor y su
    productividad laboral LP = ingreso / personal (Kutac et al., 2022). Los sueldos son información
    sensible: los demás roles no los ven. `margin` es el margen de contribución (ingreso − gasto
    operativo del conductor) y no depende del filtro de categoría."""
    mode = _iva_mode(iva_mode)
    rates = iva_config.CONFIG.rates
    category = category if category in VALID_CATEGORIES and category != "mantenimiento" else None
    drivers = client.list_drivers()
    driver_ids = {d["id"] for d in drivers}
    personnel_ok = include_fixed and date_from is not None and date_to is not None

    items = ("combustible", "peaje", "alimentacion")
    gross: dict[str, dict[str, Decimal]] = defaultdict(lambda: dict.fromkeys(items, ZERO))
    fuel_liters_by_driver: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in client.expense_aggregate(date_from, date_to):
        did = row["driver_id"]
        if did not in driver_ids or row["type"] not in _EXPENSE_FIELD:
            continue
        gross[did][row["type"]] += Decimal(str(row["amount_total"]))
        if row["type"] == "combustible":
            fuel_liters_by_driver[did] += Decimal(str(row["liters_total"]))

    trips_by_driver: dict[str, int] = defaultdict(int)
    distance_by_driver: dict[str, int] = defaultdict(int)
    revenue_by_driver: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in client.trip_aggregate(date_from, date_to):
        did = row["driver_id"]
        if did not in driver_ids:
            continue
        trips_by_driver[did] += row["trip_count"]
        distance_by_driver[did] += row["distance_km"]
        revenue_by_driver[did] += Decimal(str(row["revenue_total"]))

    personnel_by_driver: dict[str, Decimal] = defaultdict(lambda: ZERO)
    if personnel_ok:
        for row in client.personnel_cost_accrual(date_from, date_to):
            personnel_by_driver[row["driver_id"]] += Decimal(str(row["amount"]))

    summaries: list[DriverSummary] = []
    fleet_total = ZERO

    for driver in drivers:
        did = driver["id"]
        net = cost_model.apply_iva(gross[did], rates, mode)
        breakdown = DriverExpenseBreakdown(
            combustible=_q2(net["combustible"]), peaje=_q2(net["peaje"]), alimentacion=_q2(net["alimentacion"])
        )
        operating_cost = breakdown.combustible + breakdown.peaje + breakdown.alimentacion
        total_cost = getattr(breakdown, category) if category else operating_cost
        distance = distance_by_driver.get(did, 0)
        cost_per_km = (total_cost / distance) if distance > 0 else None
        fleet_total += total_cost

        revenue = revenue_by_driver.get(did, ZERO)
        has_revenue = revenue > 0
        margin = (revenue - operating_cost) if has_revenue else None

        fuel_liters = fuel_liters_by_driver.get(did, ZERO)
        fuel_efficiency = (fuel_liters / distance * 100) if distance > 0 and fuel_liters > 0 else None

        personnel = _convert("personal", personnel_by_driver[did], mode) if did in personnel_by_driver else None
        labour_productivity = revenue / personnel if (has_revenue and personnel) else None

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
                personnel_cost=_q2(personnel),
                labour_productivity=_q2(labour_productivity),
            )
        )

    return DriverSummaryResponse(
        drivers=summaries, fleet_total_cost=fleet_total, iva_mode=mode, personnel_included=personnel_ok
    )


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
    iva_mode: Optional[str] = None,
) -> TrendResponse:
    """RF-16: costo total por período (semana, mes o año) — la vista de
    tendencia que un ERP de flota (p. ej. Odoo Fleet) reporta junto al total
    acumulado, en vez de un solo número estático.

    Es la tendencia del gasto operativo (costos variables): los costos fijos se prorratean por días y
    no aportan forma a la curva. `category` (opcional) acota `total_cost` de cada punto al tipo de
    gasto seleccionado en el tablero, igual que en build_dashboard_summary."""
    mode = _iva_mode(iva_mode)
    rates = iva_config.CONFIG.rates
    category = category if category in VALID_CATEGORIES else None
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]
    vehicle_ids = {v["id"] for v in vehicles}

    buckets: dict[str, dict[str, Decimal]] = defaultdict(lambda: dict.fromkeys(cost_model.VARIABLE_ITEMS, ZERO))
    bucket_start: dict[str, date] = {}

    for row in client.expense_aggregate(date_from, date_to):
        if row["vehicle_id"] not in vehicle_ids or row["type"] not in _EXPENSE_FIELD:
            continue
        label, start = _period_bucket(date.fromisoformat(row["expense_date"]), period)
        bucket_start.setdefault(label, start)
        buckets[label][row["type"]] += Decimal(str(row["amount_total"]))

    for row in client.maintenance_aggregate(date_from, date_to):
        if row["vehicle_id"] not in vehicle_ids:
            continue
        label, start = _period_bucket(date.fromisoformat(row["performed_at"]), period)
        bucket_start.setdefault(label, start)
        buckets[label]["mantenimiento"] += Decimal(str(row["cost_total"]))

    points = []
    for label, gross in sorted(buckets.items(), key=lambda kv: bucket_start[kv[0]]):
        net = cost_model.apply_iva(gross, rates, mode)
        b = ExpenseBreakdown(
            combustible=_q2(net["combustible"]),
            peaje=_q2(net["peaje"]),
            alimentacion=_q2(net["alimentacion"]),
            mantenimiento=_q2(net["mantenimiento"]),
        )
        total = getattr(b, category) if category else b.combustible + b.peaje + b.alimentacion + b.mantenimiento
        points.append(TrendPoint(period_label=label, period_start=bucket_start[label], total_cost=total, breakdown=b))
    return TrendResponse(points=points, iva_mode=mode)


def _maintenance_by_vehicle(
    client: FleetClient, vehicle_id: Optional[str] = None, status_filter: Optional[str] = None
) -> dict[str, list[dict]]:
    """Mantenimientos de la flota agrupados por vehículo, con UNA llamada a fleet-core, sin importar
    cuántos vehículos tenga la flota (una llamada por vehículo haría crecer el costo con la flota). Dentro de cada vehículo se conserva el orden del más reciente al más
    antiguo."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in client.list_maintenance_records(vehicle_id, status_filter):
        grouped[record["vehicle_id"]].append(record)
    return grouped


def build_expense_records(
    client: FleetClient,
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    iva_mode: Optional[str] = None,
) -> list[ExpenseRecord]:
    """Insumo del histograma y la dispersión costo-vs-kilometraje del
    tablero. Los gastos de viaje (combustible/peaje/alimentación) vienen
    agregados por día desde SQL — a la escala de una flota real, "un punto
    por día" sigue mostrando la forma real de la distribución y los valores
    atípicos, sin repetir el problema de una llamada HTTP por recibo. El
    mantenimiento sigue viniendo registro por registro, pero de toda la
    flota en una sola llamada."""
    mode = _iva_mode(iva_mode)
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
                    amount=_q2(_convert(row["type"], Decimal(str(row["amount_total"])), mode)),
                    mileage_km=mileage_by_key.get((vid, row["expense_date"])),
                    occurred_at=row["expense_date"],
                )
            )

    if category is None or category == "mantenimiento":
        maintenance = _maintenance_by_vehicle(client, vehicle_id, "completado")
        for vehicle in vehicles:
            for record in maintenance.get(vehicle["id"], []):
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
                        amount=_q2(_convert("mantenimiento", Decimal(str(record["cost"])), mode)),
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
    iva_mode: Optional[str] = None,
) -> list[MaintenanceReportItem]:
    """RF-17: mantenimientos (pendientes y completados) dentro del período,
    con su costo — el detalle que el resumen de costos no desglosa registro
    por registro."""
    mode = _iva_mode(iva_mode)
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]

    items: list[MaintenanceReportItem] = []
    maintenance = _maintenance_by_vehicle(client, vehicle_id)
    for vehicle in vehicles:
        for record in maintenance.get(vehicle["id"], []):
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
                    cost=_q2(_convert("mantenimiento", Decimal(str(record["cost"])), mode)) if record.get("cost") else None,
                    performed_at=record.get("performed_at"),
                )
            )
    return items


def build_maintenance_status(
    client: FleetClient, vehicle_id: Optional[str] = None, iva_mode: Optional[str] = None
) -> MaintenanceStatus:
    """Bloque de 'acción requerida' del tablero: qué mantenimientos pendientes
    son urgentes (por kilometraje restante) y si la flota se mantiene de
    forma preventiva o a la fuerza (correctivo) — no acota por fecha, porque
    la urgencia se mide contra el kilometraje actual del vehículo, no contra
    un período de tiempo."""
    mode = _iva_mode(iva_mode)
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]

    alerts: list[MaintenanceAlertDetail] = []
    mix_by_category: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_cost": Decimal("0")})

    maintenance = _maintenance_by_vehicle(client, vehicle_id)
    for vehicle in vehicles:
        current_km = vehicle["current_mileage_km"]
        for record in maintenance.get(vehicle["id"], []):
            if record["status"] == "completado":
                if record.get("cost"):
                    entry = mix_by_category[record["category"]]
                    entry["count"] += 1
                    entry["total_cost"] += _q2(_convert("mantenimiento", Decimal(str(record["cost"])), mode))
                continue
            if record["status"] != "pendiente":
                continue

            scheduled = record.get("scheduled_mileage_km")
            # km restantes y urgencia los calcula fleet-core (RF-13): aquí no se decide.
            remaining = record.get("km_remaining")
            urgency = record.get("urgency") or alert_policy.NORMAL

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

    alerts.sort(key=lambda a: (alert_policy.RANK[a.urgency], a.km_remaining if a.km_remaining is not None else 10**9))

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

    Ver app/dashboards/ahp.py y ahp_config.json para el método, la matriz de
    comparación pareada, su procedencia y el cálculo del ratio de
    consistencia. Aplica el método AHP que Akcaer et al. (2026) y Nugraha et
    al. (2025) usan en mantenimiento ferroviario y vial, pero con un conjunto
    de criterios propio (seguridad, urgencia y costo) adaptado a una flota
    vehicular; la respuesta declara la procedencia de los juicios en `config`."""
    vehicles = client.list_vehicles()
    if vehicle_id:
        vehicles = [v for v in vehicles if v["id"] == vehicle_id]
    plate_by_id = {v["id"]: v["plate"] for v in vehicles}
    policy = client.maintenance_policy()

    # Costo histórico promedio por tipo de mantenimiento, agregado sobre
    # TODA la flota (no solo el vehículo en cuestión) para tener una muestra
    # razonable incluso con una flota piloto pequeña.
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
    pending = _maintenance_by_vehicle(client, vehicle_id, "pendiente")
    for vehicle in vehicles:
        vid = vehicle["id"]
        for record in pending.get(vid, []):
            if record["status"] != "pendiente":
                continue
            km_remaining = record.get("km_remaining")  # lo calcula fleet-core (RF-13)

            mtype = record["maintenance_type"]
            seguridad = ahp.safety_score(mtype)
            urgencia = ahp.urgency_score(km_remaining, alert_policy.threshold_for(policy, mtype))
            costo = ahp.cost_score(mtype, avg_cost_by_type)
            score = ahp.priority_score(seguridad, urgencia, costo)

            items.append(
                MaintenancePriorityItem(
                    vehicle_id=vid,
                    vehicle_plate=plate_by_id[vid],
                    maintenance_type=mtype,
                    category=record["category"],
                    km_remaining=km_remaining,
                    urgency=record.get("urgency") or alert_policy.NORMAL,
                    seguridad_score=round(seguridad, 4),
                    urgencia_score=round(urgencia, 4),
                    costo_score=round(costo, 4),
                    priority_score=round(score, 4),
                )
            )

    # A igual puntaje, primero el más vencido en km: los expertos calificaron igual de críticos los tipos de
    # mantenimiento y los propietarios deciden «por seguridad primero y luego por el kilómetro» (entrevistas, 2026).
    items.sort(key=lambda item: (-item.priority_score, ahp.km_tiebreak(item.km_remaining)))
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
        config=AhpConfigInfo(
            version=ahp.CONFIG.version,
            estado=ahp.CONFIG.estado,
            procedencia=ahp.CONFIG.procedencia,
            costo_direccion=ahp.CONFIG.costo.direccion,
        ),
    )


def build_vehicle_attention(
    client: FleetClient,
    urgency_over_cost: float = 3.0,
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    limit: int = 5,
) -> VehicleAttentionResponse:
    """RF-19: ranking de atención por vehículo, con AHP de dos criterios.

    Combina el costo relativo del vehículo en el período (el mismo total del
    resumen del tablero) con su peor urgencia de mantenimiento pendiente. La
    urgencia sale del mismo `urgency_score` que usa RF-20, así el tablero y
    la página de mantenimiento no puntúan la urgencia con escalas distintas.
    Los pesos salen de `urgency_over_cost` (escala de Saaty, 1/9 a 9)."""
    weights = ahp.weights_two_criteria(urgency_over_cost)
    summary = build_dashboard_summary(client, vehicle_id, date_from, date_to, category)
    pending = build_maintenance_priority(client, vehicle_id)

    worst_score: dict[str, float] = {}
    worst_class: dict[str, str] = {}
    for item in pending.items:
        key = str(item.vehicle_id)
        worst_score[key] = max(worst_score.get(key, 0.0), item.urgencia_score)
        if key not in worst_class or alert_policy.RANK[item.urgency] < alert_policy.RANK[worst_class[key]]:
            worst_class[key] = item.urgency

    vehicles = [
        {"vehicle_id": str(v.vehicle_id), "plate": v.plate, "total_cost": v.total_cost} for v in summary.vehicles
    ]
    ranked = ahp.rank_vehicle_attention(vehicles, worst_score, weights, limit)
    return VehicleAttentionResponse(
        items=[
            VehicleAttentionItem(
                vehicle_id=r.vehicle_id,
                vehicle_plate=r.plate,
                total_cost=Decimal(str(round(r.total_cost, 2))),
                cost_score=round(r.cost_score, 4),
                urgency_score=round(r.urgency_score, 4),
                worst_urgency=worst_class.get(r.vehicle_id, "sin_pendientes"),
                attention_score=round(r.attention_score, 4),
            )
            for r in ranked
        ],
        weights=VehicleAttentionWeights(
            urgencia=round(weights.urgencia, 4),
            costo=round(weights.costo, 4),
            urgency_over_cost=weights.urgency_over_cost,
            consistency_ratio=round(weights.consistency_ratio, 4),
        ),
    )
