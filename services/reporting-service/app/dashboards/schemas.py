"""Esquemas de respuesta de todos los endpoints del dashboard y reportes."""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ExpenseBreakdown(BaseModel):
    """RF-16: composición del gasto por tipo, para el gráfico del dashboard."""

    combustible: Decimal = Decimal("0")
    peaje: Decimal = Decimal("0")
    alimentacion: Decimal = Decimal("0")
    mantenimiento: Decimal = Decimal("0")


class CostCategoryLine(BaseModel):
    """Una de las ocho categorías del costo por kilómetro de Zysińska & Menes (2026)."""

    key: str
    label: str
    amount: Decimal
    per_km: Optional[Decimal] = None
    share_pct: Optional[Decimal] = None


class CostStructure(BaseModel):
    """Costos e indicadores de un vehículo (o de la flota) en el período (modelo de costos).

    Ct = Cv + Cf (Poliak et al., 2025); costo, ingreso y utilidad por km y margen (Zysińska & Menes,
    2026); LP y ROP (Kutac et al., 2022). Los campos que dependen de los costos fijos y de personal son
    None cuando no se incluyen (rol operador o período sin fechas): no se muestra un total incompleto
    como si fuera el total."""

    iva_mode: str
    fixed_included: bool
    distance_km: int
    variable_cost: Decimal  # Cv
    fixed_cost: Optional[Decimal] = None  # Cf
    total_cost: Optional[Decimal] = None  # Ct
    cv_per_km: Optional[Decimal] = None
    cf_per_km: Optional[Decimal] = None
    ct_per_km: Optional[Decimal] = None
    revenue: Optional[Decimal] = None
    revenue_per_km: Optional[Decimal] = None
    # % de los km del período que tienen ingreso registrado: por debajo de 100 el margen se subestima.
    revenue_coverage_pct: Optional[Decimal] = None
    profit: Optional[Decimal] = None  # U = R − Ct
    profit_per_km: Optional[Decimal] = None
    margin_pct: Optional[Decimal] = None  # U / R × 100
    contribution_margin: Optional[Decimal] = None  # R − Cv
    personnel_cost: Optional[Decimal] = None  # PC
    labour_productivity: Optional[Decimal] = None  # R / PC
    return_on_personnel_cost_pct: Optional[Decimal] = None  # U / PC × 100
    composition: list[CostCategoryLine] = []


class VehicleSummary(BaseModel):
    vehicle_id: uuid.UUID
    plate: str
    brand: str
    model: str
    current_mileage_km: int
    trip_count: int
    distance_km: int
    total_cost: Decimal
    breakdown: ExpenseBreakdown
    pending_maintenance_alerts: int
    # Rentabilidad: el título de la tesis es "control de costos", así que
    # esto es alcance adicional, no el objetivo central — revenue es None
    # cuando ningún viaje del vehículo tiene ingreso registrado todavía.
    revenue: Optional[Decimal] = None
    margin: Optional[Decimal] = None
    # Consumo real (litros/100km) — distinto del costo: el precio del
    # diésel sube y baja, el consumo delata problemas mecánicos o de manejo.
    fuel_liters: Decimal = Decimal("0")
    fuel_efficiency_l_100km: Optional[Decimal] = None
    # Proxy de disponibilidad: % de días del período con al menos un viaje
    # completado. Es una aproximación a partir de actividad registrada, NO
    # un registro real de tiempo en taller (no existe ese evento en el
    # modelo de datos) — debe presentarse con esa salvedad explícita.
    active_days: Optional[int] = None
    period_days: Optional[int] = None
    utilization_pct: Optional[Decimal] = None
    # Costos e indicadores completos del vehículo (variables y, para el admin, fijos).
    costs: Optional[CostStructure] = None


class DashboardSummary(BaseModel):
    """RF-15: costo total por vehículo (y de toda la flota).

    `fleet_total_cost` y `total_cost` de cada vehículo son el gasto operativo (costos variables), acotado
    por `category` si se pidió; `fleet_total_margin` es el margen de contribución (ingreso − costos
    variables) y NO depende del filtro de categoría. El costo total y la utilidad completos están en
    `fleet_costs` y en `costs` de cada vehículo."""

    vehicles: list[VehicleSummary]
    fleet_total_cost: Decimal
    fleet_total_revenue: Optional[Decimal] = None
    fleet_total_margin: Optional[Decimal] = None
    iva_mode: str = "bruto"
    fleet_costs: Optional[CostStructure] = None
    # None = se incluyeron los costos fijos y de personal; "rol" = el rol no los ve; "sin_periodo" = falta el período.
    fixed_costs_omitted_reason: Optional[str] = None
    # Personal de conductores sin kilómetros en el período: cuenta en el total de la flota, en ningún vehículo.
    unallocated_personnel_cost: Optional[Decimal] = None


class TrendPoint(BaseModel):
    period_label: str
    # Primer día del período del punto: permite distinguir los períodos completos del que está en curso
    # (p. ej. para estimar la variabilidad histórica sin contar un período a medias).
    period_start: Optional[date] = None
    total_cost: Decimal
    breakdown: ExpenseBreakdown


class TrendResponse(BaseModel):
    """RF-16: costo total agrupado por semana o mes (patrón 'costs over
    time' de los ERP de flota, en vez de un solo total estático)."""

    points: list[TrendPoint]
    iva_mode: str = "bruto"


class ExpenseRecord(BaseModel):
    """Un gasto individual sin agregar — insumo del histograma y la dispersión
    costo-vs-kilometraje del tablero."""

    vehicle_plate: str
    category: str
    amount: Decimal
    mileage_km: Optional[int]
    occurred_at: Optional[str]


class MaintenanceReportItem(BaseModel):
    """RF-17: una fila del reporte de mantenimientos del período."""

    vehicle_plate: str
    maintenance_type: str
    category: str
    status: str
    scheduled_mileage_km: Optional[int]
    performed_mileage_km: Optional[int]
    cost: Optional[Decimal]
    performed_at: Optional[str]


class MaintenanceAlertDetail(BaseModel):
    """Un mantenimiento pendiente con su urgencia — a diferencia del conteo
    plano que ya existía, esto le dice al gerente CUÁL vehículo y CUÁNTO
    kilometraje le queda antes de que el mantenimiento sea obligatorio."""

    vehicle_id: uuid.UUID
    vehicle_plate: str
    maintenance_type: str
    category: str
    scheduled_mileage_km: Optional[int]
    current_mileage_km: int
    km_remaining: Optional[int]
    urgency: str  # "vencido" | "proximo" | "normal"


class MaintenanceMixEntry(BaseModel):
    """Costo y conteo de mantenimientos completados por categoría
    (preventivo/correctivo/programado_km) — indicador de si la flota se
    mantiene de forma planificada o a la fuerza."""

    category: str
    count: int
    total_cost: Decimal


class MaintenanceStatus(BaseModel):
    alerts: list[MaintenanceAlertDetail]
    mix: list[MaintenanceMixEntry]


class MaintenancePriorityItem(BaseModel):
    """RF-20: un mantenimiento pendiente con su puntaje AHP y el desglose por
    criterio — se muestra el desglose, no solo el puntaje final, porque un
    ranking de decisión multicriterio que oculta cómo llegó al orden no es
    auditable (ver Akcaer et al., 2026, sobre transparencia del ranking)."""

    vehicle_id: uuid.UUID
    vehicle_plate: str
    maintenance_type: str
    category: str
    km_remaining: Optional[int]
    urgency: str = "normal"  # "vencido" | "proximo" | "normal", según la política de fleet-core (RF-13)
    seguridad_score: float
    urgencia_score: float
    costo_score: float
    priority_score: float


class AhpCriteriaWeights(BaseModel):
    """Pesos de criterios derivados por AHP (Saaty, 1980) a partir de la
    matriz de comparación pareada de ahp_config.json, y el ratio de
    consistencia que valida que la matriz es aceptable (CR < 0.10)."""

    seguridad: float
    urgencia: float
    costo: float
    consistency_ratio: float
    is_consistent: bool


class AhpConfigInfo(BaseModel):
    """Procedencia de los juicios que produjeron el ranking: sin esto un
    lector no puede distinguir pesos de un panel de expertos de pesos
    provisionales escritos por el desarrollador."""

    version: str
    estado: str
    procedencia: str
    costo_direccion: str


class MaintenancePriorityResponse(BaseModel):
    items: list[MaintenancePriorityItem]
    weights: AhpCriteriaWeights
    config: AhpConfigInfo


class VehicleAttentionItem(BaseModel):
    """RF-19: un vehículo con su costo relativo, su peor urgencia de
    mantenimiento y el puntaje de atención que combina ambos."""

    vehicle_id: uuid.UUID
    vehicle_plate: str
    total_cost: Decimal
    cost_score: float
    urgency_score: float
    worst_urgency: str  # "vencido" | "proximo" | "normal" | "sin_pendientes"
    attention_score: float


class VehicleAttentionWeights(BaseModel):
    """Pesos AHP de dos criterios para la razón de importancia elegida.
    consistency_ratio es 0 por construcción (matriz recíproca 2x2)."""

    urgencia: float
    costo: float
    urgency_over_cost: float
    consistency_ratio: float


class VehicleAttentionResponse(BaseModel):
    items: list[VehicleAttentionItem]
    weights: VehicleAttentionWeights


class DriverExpenseBreakdown(BaseModel):
    """Igual que ExpenseBreakdown pero sin mantenimiento — el mantenimiento
    es del vehículo, no depende de quién lo conducía."""

    combustible: Decimal = Decimal("0")
    peaje: Decimal = Decimal("0")
    alimentacion: Decimal = Decimal("0")


class DriverSummary(BaseModel):
    driver_id: uuid.UUID
    full_name: str
    trip_count: int
    distance_km: int
    total_cost: Decimal
    cost_per_km: Optional[Decimal]
    breakdown: DriverExpenseBreakdown
    revenue: Optional[Decimal] = None
    margin: Optional[Decimal] = None
    fuel_liters: Decimal = Decimal("0")
    fuel_efficiency_l_100km: Optional[Decimal] = None
    # Solo admin: costo de personal del conductor en el período y ingreso que genera por cada dólar de personal (LP).
    personnel_cost: Optional[Decimal] = None
    labour_productivity: Optional[Decimal] = None


class DriverSummaryResponse(BaseModel):
    """RF-16 extendido: mismo análisis de costos que por vehículo, pero por
    conductor — para ver quién genera más gasto operativo (combustible,
    peajes, alimentación) y con qué eficiencia (costo por km conducido)."""

    drivers: list[DriverSummary]
    fleet_total_cost: Decimal
    iva_mode: str = "bruto"
    personnel_included: bool = False


class RouteSummary(BaseModel):
    """Costo y distancia promedio por ruta — el contexto de dificultad que
    falta para comparar conductores de forma justa: un costo/km alto puede
    ser mala conducción, o puede ser que le tocó la ruta más cara."""

    origin: str
    destination: str
    trip_count: int
    avg_distance_km: int
    cost_total: Decimal
    cost_per_km: Optional[Decimal]


class RouteSummaryResponse(BaseModel):
    routes: list[RouteSummary]
    iva_mode: str = "bruto"
