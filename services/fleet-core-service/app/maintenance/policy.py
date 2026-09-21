"""Política de alertas de mantenimiento por kilometraje (RF-13).

ÚNICO lugar donde se decide si un mantenimiento pendiente está 'vencido',
'próximo' o 'normal'. La página de mantenimiento, el cierre de viaje y el
tablero de reporting consumen esta clasificación desde fleet-core-service en
lugar de aplicar cada uno su propio umbral.

- vencido: el kilometraje actual ya alcanzó o superó el programado (km restantes <= 0).
- próximo: faltan `proximo_km` km o menos (umbral configurable, con excepciones por tipo).
- normal: falta más, o el mantenimiento no tiene kilometraje programado.

El umbral vive en maintenance_policy.json (o en la ruta de MAINTENANCE_POLICY_PATH),
que declara su `estado` y su `procedencia`. Un archivo inválido detiene el arranque.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

VENCIDO = "vencido"
PROXIMO = "proximo"
NORMAL = "normal"
ALLOWED_TYPES = {"aceite", "filtros", "llantas", "frenos", "bocines", "otro"}

_DEFAULT_PATH = Path(__file__).with_name("maintenance_policy.json")


@dataclass(frozen=True)
class MaintenancePolicy:
    version: str
    estado: str
    procedencia: str
    proximo_km: int
    proximo_km_por_tipo: dict[str, int] = field(default_factory=dict)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"maintenance_policy inválida: {message}")


def _positive_km(value, name: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), f"{name} debe ser un entero de km")
    _require(1 <= value <= 1_000_000, f"{name}={value} fuera de [1, 1000000]")
    return value


def load_policy(path: str | os.PathLike | None = None) -> MaintenancePolicy:
    """Lee y valida la política. Ruta: argumento, luego MAINTENANCE_POLICY_PATH
    y por último el archivo junto a este módulo."""
    source = Path(path or os.getenv("MAINTENANCE_POLICY_PATH") or _DEFAULT_PATH)
    raw = json.loads(source.read_text(encoding="utf-8"))
    for key in ("version", "estado", "procedencia"):
        _require(isinstance(raw.get(key), str) and raw[key].strip(), f"falta '{key}'")
    overrides = raw.get("proximo_km_por_tipo", {})
    _require(isinstance(overrides, dict), "proximo_km_por_tipo debe ser un objeto")
    for mtype in overrides:
        _require(mtype in ALLOWED_TYPES, f"tipo desconocido en proximo_km_por_tipo: {mtype}")
    return MaintenancePolicy(
        version=raw["version"],
        estado=raw["estado"],
        procedencia=raw["procedencia"],
        proximo_km=_positive_km(raw.get("proximo_km"), "proximo_km"),
        proximo_km_por_tipo={k: _positive_km(v, f"proximo_km_por_tipo.{k}") for k, v in overrides.items()},
    )


POLICY = load_policy()


def threshold_for(maintenance_type: str, policy: MaintenancePolicy | None = None) -> int:
    policy = policy or POLICY
    return policy.proximo_km_por_tipo.get(maintenance_type, policy.proximo_km)


def km_remaining(scheduled_mileage_km: Optional[int], current_mileage_km: int) -> Optional[int]:
    return None if scheduled_mileage_km is None else scheduled_mileage_km - current_mileage_km


def classify(remaining: Optional[int], maintenance_type: str = "otro", policy: MaintenancePolicy | None = None) -> str:
    if remaining is None:
        return NORMAL
    if remaining <= 0:
        return VENCIDO
    if remaining <= threshold_for(maintenance_type, policy):
        return PROXIMO
    return NORMAL


def assess(record, current_mileage_km: int, policy: MaintenancePolicy | None = None) -> tuple[Optional[int], Optional[str]]:
    """(km restantes, urgencia) de un registro de mantenimiento. Solo los
    pendientes tienen urgencia; un mantenimiento completado devuelve (None, None)."""
    if record.status != "pendiente":
        return None, None
    remaining = km_remaining(record.scheduled_mileage_km, current_mileage_km)
    return remaining, classify(remaining, record.maintenance_type, policy)
