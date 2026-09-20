"""Endpoints del dashboard y de reportes exportables (RF-15 a RF-20) --
todos delegan la agregación a app/dashboards/service.py y solo traducen
errores de fleet-core-service a respuestas HTTP."""
from datetime import date
from typing import Callable, Optional, TypeVar

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, get_current_user
from app.core.fleet_client import FleetClient
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
)

router = APIRouter(tags=["dashboards"])

T = TypeVar("T")


def _fleet_client(current_user: CurrentUser = Depends(get_current_user)) -> FleetClient:
    """Arma un FleetClient con el token del usuario actual, para reenviarlo tal cual."""
    return FleetClient(token=current_user.token)


def _call_or_502(fn: Callable[[], T]) -> T:
    """fleet-core-service es la única fuente de datos de este servicio — si
    no responde, se lo decimos al cliente en vez de fallar en silencio."""
    try:
        return fn()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail="Error consultando fleet-core-service."
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="fleet-core-service no está disponible.")


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    client: FleetClient = Depends(_fleet_client),
) -> DashboardSummary:
    """RF-15, RF-16: costo total y composición de gastos por vehículo y periodo.
    `category` (combustible|peaje|alimentacion|mantenimiento) acota el total al
    tipo de gasto seleccionado en el tablero; el desglose completo no cambia."""
    return _call_or_502(lambda: build_dashboard_summary(client, vehicle_id, date_from, date_to, category))


@router.get("/dashboard/trend", response_model=TrendResponse)
def dashboard_trend(
    period: str = "month",
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    client: FleetClient = Depends(_fleet_client),
) -> TrendResponse:
    """RF-16: costo total agrupado por semana o mes — tendencia en el tiempo,
    no solo el acumulado del período (patrón 'costs over time' de Odoo Fleet)."""
    return _call_or_502(lambda: build_cost_trend(client, period, vehicle_id, date_from, date_to, category))


@router.get("/dashboard/records", response_model=list[ExpenseRecord])
def dashboard_records(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    client: FleetClient = Depends(_fleet_client),
) -> list[ExpenseRecord]:
    """Gastos individuales sin agregar (viajes y mantenimientos completados),
    con su kilometraje — insumo del histograma y la dispersión del tablero."""
    return _call_or_502(lambda: build_expense_records(client, vehicle_id, date_from, date_to, category))


@router.get("/dashboard/drivers", response_model=DriverSummaryResponse)
def dashboard_drivers(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    client: FleetClient = Depends(_fleet_client),
) -> DriverSummaryResponse:
    """Análisis de costo por conductor (combustible, peajes, alimentación) y
    costo por km conducido — el mantenimiento queda fuera porque es del
    vehículo, no del conductor."""
    return _call_or_502(lambda: build_driver_summary(client, date_from, date_to, category))


@router.get("/dashboard/routes", response_model=RouteSummaryResponse)
def dashboard_routes(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    client: FleetClient = Depends(_fleet_client),
) -> RouteSummaryResponse:
    """Costo y distancia por ruta — contexto de dificultad para leer el
    ranking de costo/km por conductor con justicia."""
    return _call_or_502(lambda: build_route_summary(client, date_from, date_to))


@router.get("/dashboard/maintenance-status", response_model=MaintenanceStatus)
def dashboard_maintenance_status(
    vehicle_id: Optional[str] = None,
    client: FleetClient = Depends(_fleet_client),
) -> MaintenanceStatus:
    """Bloque de 'acción requerida' del tablero: alertas de mantenimiento
    ordenadas por urgencia (km restantes) y la mezcla preventivo/correctivo
    de lo ya completado."""
    return _call_or_502(lambda: build_maintenance_status(client, vehicle_id))


@router.get("/dashboard/maintenance-priority", response_model=MaintenancePriorityResponse)
def dashboard_maintenance_priority(
    vehicle_id: Optional[str] = None,
    client: FleetClient = Depends(_fleet_client),
) -> MaintenancePriorityResponse:
    """RF-20: ranking de mantenimientos pendientes por AHP (seguridad,
    urgencia por kilometraje, costo estimado) — no solo por km restantes
    como en /dashboard/maintenance-status. Ver app/dashboards/ahp.py."""
    return _call_or_502(lambda: build_maintenance_priority(client, vehicle_id))


@router.get("/reports/maintenance", response_model=list[MaintenanceReportItem])
def maintenance_report(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    client: FleetClient = Depends(_fleet_client),
) -> list[MaintenanceReportItem]:
    """RF-17: mantenimientos del período (pendientes y completados), con costo."""
    return _call_or_502(lambda: build_maintenance_report(client, vehicle_id, date_from, date_to))


@router.get("/reports/costs.xlsx")
def export_costs_xlsx(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    client: FleetClient = Depends(_fleet_client),
) -> StreamingResponse:
    """RF-17: reporte de costos por vehículo y periodo, exportado a Excel."""
    summary = _call_or_502(lambda: build_dashboard_summary(client, vehicle_id, date_from, date_to))
    workbook_bytes = build_costs_workbook(summary)
    return StreamingResponse(
        iter([workbook_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reporte_costos.xlsx"},
    )


@router.get("/reports/costs.pdf")
def export_costs_pdf(
    vehicle_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    client: FleetClient = Depends(_fleet_client),
) -> StreamingResponse:
    """RF-17: mismo reporte de costos, exportado a PDF."""
    summary = _call_or_502(lambda: build_dashboard_summary(client, vehicle_id, date_from, date_to))
    pdf_bytes = build_costs_pdf(summary)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reporte_costos.pdf"},
    )
