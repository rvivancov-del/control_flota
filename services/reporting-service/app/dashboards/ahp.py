"""Analytic Hierarchy Process (Saaty, 1980) aplicado a la priorización de
mantenimientos pendientes — RF-20.

Por qué existe este módulo: la Base conceptual de la tesis compara este
proyecto contra literatura de priorización de mantenimiento por decisión
multicriterio (Akcaer, Öztürk y Yüksel, 2026 — AHP+TOPSIS+PROMETHEE en
mantenimiento ferroviario; Nugraha, Muhidong y Soma, 2025 — AHP+GIS en
mantenimiento vial; Liu et al., 2024 — AHP-TOPSIS en mantenimiento de
pavimento). Antes de este módulo, `build_maintenance_status` (ver
service.py) ordenaba los mantenimientos pendientes por un solo criterio
(kilometraje restante). Este módulo agrega los otros dos criterios que la
literatura revisada usa de forma consistente — costo y criticidad de
seguridad — y los combina con AHP, no con una suma ponderada arbitraria.

No se usa numpy: para una matriz de comparación pareada de 3 criterios, el
método de aproximación de Saaty (normalizar columnas, promediar filas) es
suficiente y es el mismo que se enseña como método manual en la literatura
de AHP quien no requiere resolver el problema de autovalores completo. Se
implementa también el cálculo exacto del índice de consistencia (CR) para
verificar que la matriz de comparación no es arbitraria.
"""

from dataclasses import dataclass

# Escala fundamental de Saaty (1-9): 1 = igual importancia, 3 = moderada,
# 5 = fuerte, 7 = muy fuerte, 9 = extrema. Juicio experto para este dominio:
# en flotas de carga pesada, un mantenimiento de seguridad (frenos, llantas)
# pesa más que su costo o que el kilometraje puro — un vehículo no debe
# operar con un sistema de frenos vencido solo porque "todavía falta poco
# para el próximo servicio programado".
#
# Orden de criterios: [Seguridad, Urgencia (km), Costo]
PAIRWISE_MATRIX: list[list[float]] = [
    [1.0, 3.0, 5.0],   # Seguridad vs. {Seguridad, Urgencia, Costo}
    [1 / 3, 1.0, 3.0],  # Urgencia vs. {Seguridad, Urgencia, Costo}
    [1 / 5, 1 / 3, 1.0],  # Costo vs. {Seguridad, Urgencia, Costo}
]
CRITERIA = ("seguridad", "urgencia", "costo")

# Índice aleatorio (Random Index) de Saaty para matrices de orden n — tabla
# estándar publicada en Saaty (1980), usada para calcular el Consistency
# Ratio (CR = CI / RI). RI(3) = 0.58.
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12}

# Criticidad de seguridad por tipo de mantenimiento (0-1): frenos y llantas
# son sistemas de seguridad activa/pasiva; aceite y filtros son de vida útil
# del motor, no de seguridad inmediata; bocines (suspensión/dirección) quedan
# en un punto intermedio. Juicio de dominio, documentado explícitamente para
# que el tribunal pueda auditar o ajustar el supuesto.
SAFETY_CRITICALITY: dict[str, float] = {
    "frenos": 1.0,
    "llantas": 0.8,
    "bocines": 0.6,
    "aceite": 0.3,
    "filtros": 0.2,
    "otro": 0.4,
}


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


def compute_ahp_weights(matrix: list[list[float]] = PAIRWISE_MATRIX) -> AhpWeights:
    """Deriva los pesos de criterios por el método de aproximación de Saaty
    (normalizar columnas, promediar filas) y calcula el Consistency Ratio
    para verificar que la matriz de comparación es aceptable (CR < 0.10)."""
    n = len(matrix)
    column_sums = [sum(matrix[i][j] for i in range(n)) for j in range(n)]
    normalized = [[matrix[i][j] / column_sums[j] for j in range(n)] for i in range(n)]
    weights = [sum(row) / n for row in normalized]

    # Consistency Ratio: lambda_max via A*w, luego CI = (lambda_max - n) / (n - 1),
    # CR = CI / RI(n). Una matriz perfectamente consistente da lambda_max == n.
    weighted_sum = _matrix_vector_product(matrix, weights)
    lambda_components = [weighted_sum[i] / weights[i] for i in range(n)]
    lambda_max = sum(lambda_components) / n
    consistency_index = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    random_index = RANDOM_INDEX.get(n, 1.12)
    consistency_ratio = consistency_index / random_index if random_index > 0 else 0.0

    return AhpWeights(
        seguridad=weights[0],
        urgencia=weights[1],
        costo=weights[2],
        consistency_ratio=consistency_ratio,
        is_consistent=consistency_ratio < 0.10,
    )


# Calculado una sola vez al importar el módulo — la matriz de comparación es
# un supuesto de diseño fijo, no un dato que cambie en tiempo de ejecución.
AHP_WEIGHTS = compute_ahp_weights()


def urgency_score(km_remaining: int | None, urgency_threshold_km: int) -> float:
    """1.0 = vencido; decae linealmente hasta ~0 a partir de 3x el umbral de
    'próximo' (consistente con URGENCY_THRESHOLD_KM ya definido en
    service.py para no introducir un segundo umbral que se pueda desalinear)."""
    if km_remaining is None:
        return 0.3  # sin kilometraje programado: urgencia moderada por defecto
    if km_remaining <= 0:
        return 1.0
    if km_remaining <= urgency_threshold_km:
        return 1.0 - 0.5 * (km_remaining / urgency_threshold_km)
    decay_span = urgency_threshold_km * 3
    return max(0.0, 0.5 - 0.5 * ((km_remaining - urgency_threshold_km) / decay_span))


def cost_score(maintenance_type: str, avg_cost_by_type: dict[str, float]) -> float:
    """Costo relativo (0-1) del tipo de mantenimiento frente al más caro de
    la flota, usando el costo histórico promedio real cuando existe
    (client.maintenance_aggregate) y, si no hay historial para ese tipo
    todavía, un costo de referencia fijo por tipo como respaldo."""
    fallback_costs = {"llantas": 275.0, "frenos": 150.0, "bocines": 120.0, "aceite": 55.0, "filtros": 40.0, "otro": 100.0}
    reference = dict(fallback_costs)
    reference.update({k: v for k, v in avg_cost_by_type.items() if v > 0})
    max_cost = max(reference.values()) if reference else 1.0
    cost = reference.get(maintenance_type, fallback_costs.get("otro", 100.0))
    return cost / max_cost if max_cost > 0 else 0.0


def priority_score(seguridad: float, urgencia: float, costo: float, weights: AhpWeights = AHP_WEIGHTS) -> float:
    """Combina los 3 subpuntajes (0-1 cada uno) con los pesos AHP en un único
    puntaje de prioridad -- más alto significa atender primero."""
    return weights.seguridad * seguridad + weights.urgencia * urgencia + weights.costo * costo
