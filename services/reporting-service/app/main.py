"""Punto de entrada de reporting-service: sin base de datos propia -- agrega
el dashboard y los reportes llamando a fleet-core-service por HTTP."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config_guard import assert_secure_configuration
from app.dashboards.router import router as dashboards_router

# RNF-02: fuera de desarrollo no arranca con secretos por defecto (este servicio no usa PostgreSQL).
assert_secure_configuration("reporting-service", uses_database=False)

app = FastAPI(title="reporting-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboards_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Chequeo de salud del contenedor (usado por docker-compose y monitoreo)."""
    return {"status": "ok", "service": "reporting-service"}
