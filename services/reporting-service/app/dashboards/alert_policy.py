"""Vocabulario y ayudas de la política de alertas de mantenimiento (RF-13).

La CLASIFICACIÓN vencido / próximo / normal la decide fleet-core-service
(app/maintenance/policy.py) y llega ya calculada en cada registro
(`urgency`, `km_remaining`); este servicio no aplica un umbral propio. Aquí
solo viven los nombres de los niveles y la lectura del umbral por tipo, que
la curva de urgencia del AHP necesita como ancla.
"""
VENCIDO = "vencido"
PROXIMO = "proximo"
NORMAL = "normal"
RANK = {VENCIDO: 0, PROXIMO: 1, NORMAL: 2}


def threshold_for(policy: dict, maintenance_type: str) -> int:
    """Umbral 'próximo' (km) de un tipo de mantenimiento según la política que
    entrega fleet-core (`GET /maintenance/policy`)."""
    return int(policy.get("proximo_km_por_tipo", {}).get(maintenance_type, policy["proximo_km"]))
