"""Clasificación de urgencia de un mantenimiento pendiente (RF-13).

Un solo punto de decisión para el estado 'vencido' / 'proximo' / 'normal' en
reporting-service. El umbral de 'próximo' sale de la configuración del AHP
(ahp_config.json → urgencia.proximo_km) para que la alerta del tablero y la
curva de urgencia del ranking no puedan desalinearse.
"""
from app.dashboards import ahp

VENCIDO = "vencido"
PROXIMO = "proximo"
NORMAL = "normal"


def classify_urgency(km_remaining: int | None, proximo_km: int | None = None) -> str:
    """Sin kilometraje programado el mantenimiento es 'normal' (no hay contra
    qué medir); <= 0 km restantes es 'vencido'; hasta `proximo_km` es 'proximo'."""
    threshold = proximo_km if proximo_km is not None else ahp.CONFIG.urgencia.proximo_km
    if km_remaining is None:
        return NORMAL
    if km_remaining <= 0:
        return VENCIDO
    if km_remaining <= threshold:
        return PROXIMO
    return NORMAL
