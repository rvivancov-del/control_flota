"""Análisis de sensibilidad del ranking AHP (RF-20).

Nugraha et al. (2025) verifican que su ranking no cambia al mover +10 % los
pesos de los criterios principales. Este módulo hace el mismo ejercicio con el
ranking de mantenimientos del prototipo: perturba cada peso en +-delta,
renormaliza y mide qué tanto cambia el orden (tau de Kendall) y si el primer
lugar y el top-3 se mantienen. No se usa en las peticiones HTTP: lo consumen
las pruebas y el informe de resultados.
"""
from dataclasses import dataclass
from itertools import combinations

from app.dashboards import ahp


def kendall_tau(order_a: list[str], order_b: list[str]) -> float:
    """Tau de Kendall (versión a) entre dos ordenamientos del mismo conjunto:
    1.0 = mismo orden, -1.0 = orden invertido."""
    if set(order_a) != set(order_b):
        raise ValueError("Los dos ordenamientos deben contener los mismos elementos")
    position_b = {item: i for i, item in enumerate(order_b)}
    pairs = list(combinations(order_a, 2))
    if not pairs:
        return 1.0
    concordant = sum(1 for x, y in pairs if position_b[x] < position_b[y])
    return (2 * concordant - len(pairs)) / len(pairs)


def perturb_weights(weights: ahp.AhpWeights, criterion: str, delta: float) -> ahp.AhpWeights:
    """Multiplica el peso de `criterion` por (1 + delta) y renormaliza a suma 1."""
    if criterion not in ahp.CRITERIA:
        raise ValueError(f"criterio desconocido: {criterion}")
    raw = weights.as_dict()
    raw[criterion] *= 1.0 + delta
    total = sum(raw.values())
    return ahp.AhpWeights(
        seguridad=raw["seguridad"] / total,
        urgencia=raw["urgencia"] / total,
        costo=raw["costo"] / total,
        consistency_ratio=weights.consistency_ratio,
        is_consistent=weights.is_consistent,
    )


def rank_items(items: list[dict], weights: ahp.AhpWeights) -> list[str]:
    """Ids ordenados de mayor a menor prioridad. Cada item trae id, seguridad,
    urgencia y costo (subpuntajes 0-1). Desempata por id para ser determinista."""
    scored = [(ahp.priority_score(i["seguridad"], i["urgencia"], i["costo"], weights), i["id"]) for i in items]
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [item_id for _, item_id in scored]


@dataclass(frozen=True)
class SensitivityRow:
    criterion: str
    delta: float
    tau: float
    top1_same: bool
    top3_same: bool


def sensitivity(
    items: list[dict],
    weights: ahp.AhpWeights | None = None,
    deltas: tuple[float, ...] = (-0.3, -0.2, -0.1, 0.1, 0.2, 0.3),
) -> list[SensitivityRow]:
    weights = weights or ahp.AHP_WEIGHTS
    baseline = rank_items(items, weights)
    rows = []
    for criterion in ahp.CRITERIA:
        for delta in deltas:
            perturbed = rank_items(items, perturb_weights(weights, criterion, delta))
            rows.append(
                SensitivityRow(
                    criterion=criterion,
                    delta=delta,
                    tau=kendall_tau(baseline, perturbed),
                    top1_same=baseline[0] == perturbed[0],
                    top3_same=set(baseline[:3]) == set(perturbed[:3]),
                )
            )
    return rows


def standard_item_set() -> list[dict]:
    """18 mantenimientos sintéticos: los 6 tipos de la configuración por 3
    estados de urgencia (vencido, próximo, lejano). Cubre todas las
    combinaciones de criticidad y urgencia sin depender de datos reales."""
    items = []
    for mtype in ("frenos", "llantas", "bocines", "aceite", "filtros", "otro"):
        for label, km in (("vencido", -200), ("proximo", 800), ("lejano", 3500)):
            items.append(
                {
                    "id": f"{mtype}-{label}",
                    "seguridad": ahp.safety_score(mtype),
                    "urgencia": ahp.urgency_score(km),
                    "costo": ahp.cost_score(mtype, {}),
                }
            )
    return items


def markdown_report(items: list[dict] | None = None) -> str:
    """Tabla en Markdown del análisis de sensibilidad con la configuración vigente."""
    items = items or standard_item_set()
    rows = sensitivity(items)
    lines = [
        f"Configuración: versión {ahp.CONFIG.version} · estado {ahp.CONFIG.estado}",
        f"Pesos: seguridad {ahp.AHP_WEIGHTS.seguridad:.4f} · urgencia {ahp.AHP_WEIGHTS.urgencia:.4f} · "
        f"costo {ahp.AHP_WEIGHTS.costo:.4f} · CR {ahp.AHP_WEIGHTS.consistency_ratio:.4f}",
        f"Conjunto: {len(items)} mantenimientos sintéticos (6 tipos × 3 estados de urgencia)",
        "",
        "| Criterio | Cambio del peso | τ de Kendall | Mismo 1.º | Mismo top-3 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.criterion} | {r.delta:+.0%} | {r.tau:.3f} | {'sí' if r.top1_same else 'no'} | "
            f"{'sí' if r.top3_same else 'no'} |"
        )
    worst = min(r.tau for r in rows)
    lines += ["", f"τ mínimo global: {worst:.3f}"]
    return "\n".join(lines)


if __name__ == "__main__":
    print(markdown_report())
