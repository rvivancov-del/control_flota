"""Exportación del resumen de costos a Excel y PDF (RF-17)."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.dashboards.schemas import DashboardSummary

_HEADERS = [
    "Placa",
    "Marca",
    "Modelo",
    "Km actual",
    "Viajes",
    "Combustible",
    "Peajes",
    "Alimentación",
    "Mantenimiento",
    "Total",
    "Alertas de mantenimiento",
]


def build_costs_workbook(summary: DashboardSummary) -> bytes:
    """RF-17: reporte de costos y mantenimientos por vehículo, exportable a Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Costos por vehiculo"

    ws.append(_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for v in summary.vehicles:
        ws.append(
            [
                v.plate,
                v.brand,
                v.model,
                v.current_mileage_km,
                v.trip_count,
                float(v.breakdown.combustible),
                float(v.breakdown.peaje),
                float(v.breakdown.alimentacion),
                float(v.breakdown.mantenimiento),
                float(v.total_cost),
                v.pending_maintenance_alerts,
            ]
        )

    ws.append([])
    total_row = ["TOTAL FLOTA", "", "", "", "", "", "", "", "", float(summary.fleet_total_cost), ""]
    ws.append(total_row)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = max(length + 2, 10)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


_PDF_HEADERS = [
    "Placa",
    "Marca/Modelo",
    "Km actual",
    "Viajes",
    "Combustible",
    "Peajes",
    "Alimentación",
    "Mantenimiento",
    "Total",
    "Alertas",
]


def build_costs_pdf(summary: DashboardSummary) -> bytes:
    """RF-17: mismo reporte de costos por vehículo, exportado a PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Reporte de costos - FlotaControl")
    styles = getSampleStyleSheet()

    story = [
        Paragraph("FlotaControl — Reporte de costos por vehículo", styles["Title"]),
        Spacer(1, 14),
    ]

    data = [_PDF_HEADERS]
    for v in summary.vehicles:
        data.append(
            [
                v.plate,
                f"{v.brand} {v.model}",
                str(v.current_mileage_km),
                str(v.trip_count),
                f"{v.breakdown.combustible:.2f}",
                f"{v.breakdown.peaje:.2f}",
                f"{v.breakdown.alimentacion:.2f}",
                f"{v.breakdown.mantenimiento:.2f}",
                f"{v.total_cost:.2f}",
                str(v.pending_maintenance_alerts),
            ]
        )
    data.append(["TOTAL FLOTA", "", "", "", "", "", "", "", f"{summary.fleet_total_cost:.2f}", ""])

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14283f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#eef1f4")]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()
