"""Punto de entrada de auth-service: arma la app FastAPI, habilita CORS para
el frontend y monta los routers de autenticación, usuarios y roles."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, roles, users

app = FastAPI(title="auth-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Chequeo de salud del contenedor (usado por docker-compose y monitoreo)."""
    return {"status": "ok", "service": "auth-service"}
