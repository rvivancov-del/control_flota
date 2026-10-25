"""Endpoints del dashboard y de reportes exportables (RF-15 a RF-20) --
todos delegan la agregación a app/dashboards/service.py y solo traducen
errores de fleet-core-service a respuestas HTTP."""
from datetime import date
from typing import Callable, Optional, TypeVar

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.deps import ADMIN, ROLES_OPERATIVOS, CurrentUser, get_current_user, require_role
from app.core.fleet_client import FleetClient
from app.dashboards import cost_model, iva_config
from app.dashboards.export import build_costs_pdf, build_costs_workbook
from app.dashboards.schemas import (
    DashboardSummary,
    DriverSummaryResponse,
    ExpenseRecord,
    MaintenancePriorityResponse,
    MaintenanceReportItem,
    MaintenanceStatus,
    RouteSummaryResponse,
    TrendResponse,
    VehicleAttentionResponse,
)
from app.dashboards.service import (
    build_cost_trend,
    build_dashboard_summary,
    build_driver_summary,
    build_expense_records,
    build_maintenance_priority,
    build_maintenance_report,
    build_maintenance_status,
    build_route_summary,
    build_vehicle_attention,
)

router = APIRouter(tags=["dashboards"], dependencies=[Depends(require_role(*ROLES_OPERATIVOS))])

T = TypeVar("T")


def _fleet_client(current_user: CurrentUser = Depends(get_current_user)) -> FleetClient:
    """Arma un FleetClient con el token del usuario actual, para reenviarlo tal cual."""
    return FleetClient(token=current_user.token)


def _iva_query(
    iva_mode: Optional[str] = Query(
        None, description="'bruto' (montos pagados, con IVA) o 'neto' (sin IVA); por defecto el de iva_config.json"
    ),
) -> str:
    """Modo de IVA pedido; cualquier otro valor es un error del cliente."""
    mode = iva_mode or iva_config.CONFIG.default_mode
    if mode not in iva_config.MODES:
        raise HTTPException(status_code=422, detail=f"iva_mode debe ser uno de: {', '.join(iva_config.MODES)}")
    return mode


def _sees_fixed_costs(current_user: CurrentUser) -> bool:
    """Los costos fijos y de personal son información financiera (y sueldos): solo el rol admin los ve."""
    return current_user.role == ADMIN


def _call_or_502(fn: Callable[[], T]) -> T:
    """fleet-core-service es la única fuente de datos de este servicio — si
    no responde, se lo decimos al cliente en vez de fallar en silencio."""
    try:
        return fn()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail="Error consultando fleet-core-service."
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="fleet-core-service no está disponible.") from exc


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
    current_user: CurrentUser = Depends(get_current_user),
) -> DashboardSummary:
    """RF-15, RF-16 y modelo de costos: gasto operativo y composición por vehículo y periodo.
    `category` (combustible|peaje|alimentacion|mantenimiento) acota el total al
    tipo de gasto seleccionado en el tablero; el desglose completo y los indicadores no cambian.
    Para el admin y con `date_from`/`date_to`, `costs` incluye costos fijos y de personal (Ct = Cv + Cf)."""
    return _call_or_502(
        lambda: build_dashboard_summary(
            client, vehicle_id, date_from, date_to, category, iva_mode, include_fixed=_sees_fixed_costs(current_user)
        )
    )


@router.get("/dashboard/trend", response_model=TrendResponse)
def dashboard_trend(
    period: str = "month",
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
) -> TrendResponse:
    """RF-16: costo total agrupado por semana o mes — tendencia en el tiempo,
    no solo el acumulado del período (patrón 'costs over time' de Odoo Fleet)."""
    return _call_or_502(lambda: build_cost_trend(client, period, vehicle_id, date_from, date_to, category, iva_mode))


@router.get("/dashboard/records", response_model=list[ExpenseRecord])
def dashboard_records(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
) -> list[ExpenseRecord]:
    """Gastos individuales sin agregar (viajes y mantenimientos completados),
    con su kilometraje — insumo del histograma y la dispersión del tablero."""
    return _call_or_502(lambda: build_expense_records(client, vehicle_id, date_from, date_to, category, iva_mode))


@router.get("/dashboard/drivers", response_model=DriverSummaryResponse)
def dashboard_drivers(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
    current_user: CurrentUser = Depends(get_current_user),
) -> DriverSummaryResponse:
    """Análisis de costo por conductor (combustible, peajes, alimentación) y
    costo por km conducido — el mantenimiento queda fuera porque es del
    vehículo, no del conductor. Solo el admin (y con período) ve además el costo de
    personal del conductor y su productividad laboral."""
    return _call_or_502(
        lambda: build_driver_summary(
            client, date_from, date_to, category, iva_mode, include_fixed=_sees_fixed_costs(current_user)
        )
    )


@router.get("/dashboard/routes", response_model=RouteSummaryResponse)
def dashboard_routes(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
) -> RouteSummaryResponse:
    """Costo y distancia por ruta — contexto de dificultad para leer el
    ranking de costo/km por conductor con justicia."""
    return _call_or_502(lambda: build_route_summary(client, date_from, date_to, iva_mode))


@router.get("/dashboard/maintenance-status", response_model=MaintenanceStatus)
def dashboard_maintenance_status(
    vehicle_id: Optional[str] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
) -> MaintenanceStatus:
    """Bloque de 'acción requerida' del tablero: alertas de mantenimiento
    ordenadas por urgencia (km restantes) y la mezcla preventivo/correctivo
    de lo ya completado."""
    return _call_or_502(lambda: build_maintenance_status(client, vehicle_id, iva_mode))


@router.get("/dashboard/maintenance-priority", response_model=MaintenancePriorityResponse)
def dashboard_maintenance_priority(
    vehicle_id: Optional[str] = None,
    client: FleetClient = Depends(_fleet_client),
) -> MaintenancePriorityResponse:
    """RF-20: ranking de mantenimientos pendientes por AHP (seguridad,
    urgencia por kilometraje, costo estimado) — no solo por km restantes
    como en /dashboard/maintenance-status. Ver app/dashboards/ahp.py."""
    return _call_or_502(lambda: build_maintenance_priority(client, vehicle_id))


@router.get("/dashboard/vehicle-attention", response_model=VehicleAttentionResponse)
def dashboard_vehicle_attention(
    urgency_over_cost: float = Query(3.0, ge=1 / 9, le=9, description="Razón de Saaty: cuántas veces más importante es la urgencia que el costo"),
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    limit: int = Query(5, ge=1, le=50),
    client: FleetClient = Depends(_fleet_client),
) -> VehicleAttentionResponse:
    """RF-19: ranking de atención por vehículo (costo relativo + peor urgencia
    de mantenimiento) con AHP de dos criterios. Usa el mismo motor y la misma
    escala de urgencia que RF-20 (ver app/dashboards/ahp.py)."""
    return _call_or_502(
        lambda: build_vehicle_attention(client, urgency_over_cost, vehicle_id, date_from, date_to, category, limit)
    )


@router.get("/reports/maintenance", response_model=list[MaintenanceReportItem])
def maintenance_report(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
) -> list[MaintenanceReportItem]:
    """RF-17: mantenimientos del período (pendientes y completados), con costo."""
    return _call_or_502(lambda: build_maintenance_report(client, vehicle_id, date_from, date_to, iva_mode))


@router.get("/reports/costs.xlsx", dependencies=[Depends(require_role(ADMIN))])
def export_costs_xlsx(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
) -> StreamingResponse:
    """RF-17: reporte de costos por vehículo y periodo, exportado a Excel (solo admin, RF-03).
    Incluye costos fijos y de personal cuando se indican `date_from` y `date_to`."""
    summary = _call_or_502(
        lambda: build_dashboard_summary(client, vehicle_id, date_from, date_to, iva_mode=iva_mode, include_fixed=True)
    )
    workbook_bytes = build_costs_workbook(summary)
    return StreamingResponse(
        iter([workbook_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reporte_costos.xlsx"},
    )


@router.get("/reports/costs.pdf", dependencies=[Depends(require_role(ADMIN))])
def export_costs_pdf(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    iva_mode: str = Depends(_iva_query),
    client: FleetClient = Depends(_fleet_client),
) -> StreamingResponse:
    """RF-17: mismo reporte de costos, exportado a PDF (solo admin, RF-03)."""
    summary = _call_or_502(
        lambda: build_dashboard_summary(client, vehicle_id, date_from, date_to, iva_mode=iva_mode, include_fixed=True)
    )
    pdf_bytes = build_costs_pdf(summary)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reporte_costos.pdf"},
    )


@router.get("/dashboard/cost-model")
def dashboard_cost_model() -> dict:
    """Metodología del modelo de costos: correspondencia entre las ocho categorías de Zysińska & Menes
    (2026) y los rubros del prototipo, fórmula y fuente de cada indicador, y las tarifas de IVA vigentes
    con su estado. Es la misma tabla que usan la interfaz y la documentación (una sola fuente)."""
    cfg = iva_config.CONFIG
    return {
        "categories": cost_model.category_map(),
        "indicators": [
            {"id": i.id, "name": i.name, "formula": i.formula, "source": i.source, "where": i.where}
            for i in cost_model.INDICATORS
        ],
        "iva": {
            "version": cfg.version,
            "estado": cfg.estado,
            "procedencia": cfg.procedencia,
            "modo_por_defecto": cfg.default_mode,
            "tarifas": {item: float(rate) for item, rate in cfg.rates.items()},
        },
    }
