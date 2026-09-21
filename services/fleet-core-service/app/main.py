"""Punto de entrada de fleet-core-service: el microservicio dueño del
esquema "fleet" -- vehículos, conductores, viajes, gastos, mantenimiento,
analítica agregada y el portal de despacho por código QR."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics.router import router as analytics_router
from app.despacho.router import router as despacho_router
from app.drivers.router import router as drivers_router
from app.expenses.router import query_router as expenses_query_router
from app.expenses.router import router as expenses_router
from app.maintenance.router import router as maintenance_router
from app.trips.router import router as trips_router
from app.vehicles.router import router as vehicles_router

app = FastAPI(title="fleet-core-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicles_router)
app.include_router(drivers_router)
app.include_router(trips_router)
app.include_router(expenses_router)
app.include_router(expenses_query_router)
app.include_router(maintenance_router)
app.include_router(analytics_router)
app.include_router(despacho_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Chequeo de salud del contenedor (usado por docker-compose y monitoreo)."""
    return {"status": "ok", "service": "fleet-core-service"}
