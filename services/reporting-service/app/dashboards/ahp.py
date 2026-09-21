"""Analytic Hierarchy Process (Saaty, 1980) aplicado a la priorización de
mantenimientos pendientes (RF-20) y a la atención por vehículo (RF-19).

Qué hace este módulo: deriva los pesos de tres criterios -- seguridad,
urgencia por kilometraje y costo -- a partir de una matriz de comparación
pareada, verifica su consistencia (CR < 0.10) y los combina en un puntaje de
prioridad por suma ponderada. RF-19 reutiliza el mismo motor con dos criterios
(urgencia y costo) y la razón de importancia que elige el usuario.

Qué NO afirma: (1) que los tres criterios sean "los que la literatura usa de
forma consistente" -- son una decisión de diseño del autor; Akcaer et al.
(2026), Nugraha et al. (2025), Liu et al. (2024) y Chaipetch et al. (2022)
aplican AHP a mantenimiento de infraestructura ferroviaria y vial con otros
conjuntos de criterios y paneles de 5 a 20 decisores. (2) que los valores por
defecto provengan de expertos: viven en ahp_config.json, que declara su
`estado` y su `procedencia` y se reemplaza con la agregación de los juicios
del panel de expertos (07_MATRICES_DE_ANALISIS/ahp_juicios_expertos.xlsx).

Ninguna constante de juicio está escrita en este archivo: la matriz, la
criticidad de seguridad, la dirección del costo, los costos de respaldo y la
curva de urgencia salen de ahp_config.json (o de la ruta en AHP_CONFIG_PATH) y
se validan al importar. Un archivo inválido o con CR >= 0.10 detiene el
arranque en vez de degradar en silencio.
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path

# Tabla estándar del Índice Aleatorio (RI) de Saaty (1980), n = 1..10.
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
CRITERIA = ("seguridad", "urgencia", "costo")
CONSISTENCY_LIMIT = 0.10  # umbral de Saaty (1980)

DIR_MAYOR = "mayor_costo_mayor_prioridad"
DIR_MENOR = "menor_costo_mayor_prioridad"
DIR_INDIFERENTE = "indiferente"
_DIRECCIONES = (DIR_MAYOR, DIR_MENOR, DIR_INDIFERENTE)

_DEFAULT_CONFIG_PATH = Path(__file__).with_name("ahp_config.json")


# --------------------------------------------------------------------------
# Núcleo matemático
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AhpWeights:
    seguridad: float
    urgencia: float
    costo: float
    consistency_ratio: float
    is_consistent: bool  # CR < 0.10, umbral estándar de Saaty (1980)

    def as_dict(self) -> dict[str, float]:
        return {"seguridad": self.seguridad, "urgencia": self.urgencia, "costo": self.costo}


def _matrix_vector_product(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def _weights_and_cr(matrix: list[list[float]]) -> tuple[list[float], float]:
    """Pesos por el método de aproximación de Saaty (normalizar columnas y
    promediar filas) y razón de consistencia CR = CI / RI(n), con
    CI = (lambda_max - n) / (n - 1). Una matriz perfectamente consistente da
    lambda_max == n. Para n <= 2 el CR es 0 por construcción (RI = 0)."""
    n = len(matrix)
    column_sums = [sum(matrix[i][j] for i in range(n)) for j in range(n)]
    normalized = [[matrix[i][j] / column_sums[j] for j in range(n)] for i in range(n)]
    weights = [sum(row) / n for row in normalized]
    weighted_sum = _matrix_vector_product(matrix, weights)
    lambda_max = sum(weighted_sum[i] / weights[i] for i in range(n)) / n
    consistency_index = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    random_index = RANDOM_INDEX.get(n, 1.49)
    consistency_ratio = consistency_index / random_index if random_index > 0 else 0.0
    return weights, consistency_ratio


# --------------------------------------------------------------------------
# Configuración externa (ahp_config.json)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class UrgencyConfig:
    proximo_km: int
    sin_urgencia_km: int
    puntaje_en_proximo: float
    puntaje_sin_kilometraje: float


@dataclass(frozen=True)
class CostConfig:
    direccion: str
    respaldo_usd: dict[str, float]


@dataclass(frozen=True)
class AhpConfig:
    version: str
    estado: str
    procedencia: str
    matrix: list[list[float]]
    criticidad_seguridad: dict[str, float]
    costo: CostConfig
    urgencia: UrgencyConfig


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"ahp_config inválido: {message}")


def _number(value, name: str, low: float, high: float) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name} debe ser numérico")
    _require(low <= float(value) <= high, f"{name}={value} fuera de [{low}, {high}]")
    return float(value)


def load_config(path: str | os.PathLike | None = None) -> AhpConfig:
    """Lee y valida la configuración del AHP. Ruta: argumento, luego la
    variable AHP_CONFIG_PATH y por último el archivo junto a este módulo."""
    source = Path(path or os.getenv("AHP_CONFIG_PATH") or _DEFAULT_CONFIG_PATH)
    raw = json.loads(source.read_text(encoding="utf-8"))

    _require(tuple(raw.get("criterios", ())) == CRITERIA, f"criterios debe ser {list(CRITERIA)}")
    for key in ("version", "estado", "procedencia"):
        _require(isinstance(raw.get(key), str) and raw[key].strip(), f"falta '{key}'")

    comp = raw.get("comparaciones_saaty", {})
    a12 = _number(comp.get("seguridad_vs_urgencia"), "seguridad_vs_urgencia", 1 / 9, 9)
    a13 = _number(comp.get("seguridad_vs_costo"), "seguridad_vs_costo", 1 / 9, 9)
    a23 = _number(comp.get("urgencia_vs_costo"), "urgencia_vs_costo", 1 / 9, 9)
    matrix = [[1.0, a12, a13], [1 / a12, 1.0, a23], [1 / a13, 1 / a23, 1.0]]
    _, cr = _weights_and_cr(matrix)
    _require(cr < CONSISTENCY_LIMIT, f"la matriz de comparación es inconsistente (CR={cr:.4f} >= {CONSISTENCY_LIMIT})")

    crit = raw.get("criticidad_seguridad", {})
    _require("otro" in crit, "criticidad_seguridad debe incluir 'otro'")
    criticidad = {k: _number(v, f"criticidad_seguridad.{k}", 0.0, 1.0) for k, v in crit.items()}

    cost = raw.get("costo", {})
    _require(cost.get("direccion") in _DIRECCIONES, f"costo.direccion debe ser una de {list(_DIRECCIONES)}")
    respaldo = cost.get("respaldo_usd", {})
    _require("otro" in respaldo, "costo.respaldo_usd debe incluir 'otro'")
    respaldo = {k: _number(v, f"costo.respaldo_usd.{k}", 0.01, 1e9) for k, v in respaldo.items()}

    u = raw.get("urgencia", {})
    proximo = _number(u.get("proximo_km"), "urgencia.proximo_km", 1, 1e6)
    sin_urgencia = _number(u.get("sin_urgencia_km"), "urgencia.sin_urgencia_km", 1, 1e6)
    _require(proximo < sin_urgencia, "urgencia.proximo_km debe ser menor que urgencia.sin_urgencia_km")
    en_proximo = _number(u.get("puntaje_en_proximo"), "urgencia.puntaje_en_proximo", 0.01, 0.99)
    sin_km = _number(u.get("puntaje_sin_kilometraje"), "urgencia.puntaje_sin_kilometraje", 0.0, 1.0)

    return AhpConfig(
        version=raw["version"],
        estado=raw["estado"],
        procedencia=raw["procedencia"],
        matrix=matrix,
        criticidad_seguridad=criticidad,
        costo=CostConfig(direccion=cost["direccion"], respaldo_usd=respaldo),
        urgencia=UrgencyConfig(int(proximo), int(sin_urgencia), en_proximo, sin_km),
    )


CONFIG = load_config()


def compute_ahp_weights(matrix: list[list[float]] | None = None) -> AhpWeights:
    """Pesos de los tres criterios y su razón de consistencia."""
    weights, consistency_ratio = _weights_and_cr(matrix if matrix is not None else CONFIG.matrix)
    return AhpWeights(
        seguridad=weights[0],
        urgencia=weights[1],
        costo=weights[2],
        consistency_ratio=consistency_ratio,
        is_consistent=consistency_ratio < CONSISTENCY_LIMIT,
    )


AHP_WEIGHTS = compute_ahp_weights()


# --------------------------------------------------------------------------
# Puntajes por criterio (0-1) y combinación
# --------------------------------------------------------------------------
def safety_score(maintenance_type: str, criticidad: dict[str, float] | None = None) -> float:
    table = criticidad if criticidad is not None else CONFIG.criticidad_seguridad
    return table.get(maintenance_type, table["otro"])


def urgency_score(km_remaining: int | None, cfg: UrgencyConfig | None = None) -> float:
    """1.0 = vencido; baja linealmente hasta `puntaje_en_proximo` al llegar a
    `proximo_km` y de ahí hasta 0 en `sin_urgencia_km`. Sin kilometraje
    programado devuelve `puntaje_sin_kilometraje`."""
    cfg = cfg or CONFIG.urgencia
    if km_remaining is None:
        return cfg.puntaje_sin_kilometraje
    if km_remaining <= 0:
        return 1.0
    if km_remaining <= cfg.proximo_km:
        return 1.0 - (1.0 - cfg.puntaje_en_proximo) * (km_remaining / cfg.proximo_km)
    span = cfg.sin_urgencia_km - cfg.proximo_km
    return max(0.0, cfg.puntaje_en_proximo * (1.0 - (km_remaining - cfg.proximo_km) / span))


def cost_score(maintenance_type: str, avg_cost_by_type: dict[str, float], cfg: CostConfig | None = None) -> float:
    """Costo relativo (0-1) frente al tipo más caro, con el promedio histórico
    real cuando existe y el costo de respaldo de la configuración si no. La
    dirección decide si más caro sube (mayor), baja (menor) o no altera
    (indiferente: 0.5 constante) la prioridad."""
    cfg = cfg or CONFIG.costo
    if cfg.direccion == DIR_INDIFERENTE:
        return 0.5
    reference = dict(cfg.respaldo_usd)
    reference.update({k: v for k, v in avg_cost_by_type.items() if v > 0})
    max_cost = max(reference.values())
    relative = reference.get(maintenance_type, cfg.respaldo_usd["otro"]) / max_cost
    return relative if cfg.direccion == DIR_MAYOR else 1.0 - relative


def priority_score(seguridad: float, urgencia: float, costo: float, weights: AhpWeights | None = None) -> float:
    """Suma ponderada de los tres subpuntajes (0-1): más alto = atender primero."""
    weights = weights or AHP_WEIGHTS
    return weights.seguridad * seguridad + weights.urgencia * urgencia + weights.costo * costo


# --------------------------------------------------------------------------
# RF-19: atención por vehículo con dos criterios (urgencia vs costo)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TwoCriteriaWeights:
    urgencia: float
    costo: float
    urgency_over_cost: float
    # Una matriz recíproca 2x2 es consistente por construcción (RI(2) = 0):
    # el CR es 0 siempre y no aporta verificación real.
    consistency_ratio: float


def weights_two_criteria(urgency_over_cost: float) -> TwoCriteriaWeights:
    """Pesos {urgencia, costo} para 'la urgencia es `a` veces más importante que
    el costo' (escala de Saaty, 1/9 <= a <= 9): a/(a+1) y 1/(a+1)."""
    a = float(urgency_over_cost)
    if not (1 / 9 <= a <= 9):
        raise ValueError("urgency_over_cost debe estar entre 1/9 y 9 (escala de Saaty)")
    weights, cr = _weights_and_cr([[1.0, a], [1.0 / a, 1.0]])
    return TwoCriteriaWeights(urgencia=weights[0], costo=weights[1], urgency_over_cost=a, consistency_ratio=cr)


@dataclass(frozen=True)
class VehicleAttention:
    vehicle_id: str
    plate: str
    total_cost: float
    cost_score: float
    urgency_score: float
    attention_score: float


def rank_vehicle_attention(
    vehicles: list[dict], urgency_by_vehicle: dict[str, float], weights: TwoCriteriaWeights, limit: int = 5
) -> list[VehicleAttention]:
    """Ordena vehículos por `w_urgencia * peor urgencia + w_costo * costo
    relativo`. `vehicles` trae vehicle_id, plate y total_cost; la urgencia
    viene del mismo `urgency_score` que usa RF-20, no de una escala aparte."""
    max_cost = max((float(v["total_cost"]) for v in vehicles), default=0.0)
    max_cost = max_cost if max_cost > 0 else 1.0
    ranked = []
    for v in vehicles:
        cost = float(v["total_cost"])
        rel_cost = cost / max_cost
        urgency = urgency_by_vehicle.get(v["vehicle_id"], 0.0)
        score = weights.urgencia * urgency + weights.costo * rel_cost
        if score > 0:
            ranked.append(VehicleAttention(v["vehicle_id"], v["plate"], cost, rel_cost, urgency, score))
    ranked.sort(key=lambda item: (-item.attention_score, item.plate))
    return ranked[:limit]
