"""Prueba unitaria de la metodología AHP (RF-20) — no requiere el stack
levantado, valida directamente la matemática de app/dashboards/ahp.py:
que los pesos sumen 1, que la matriz de comparación sea consistente
(CR < 0.10, umbral estándar de Saaty, 1980), y que los puntajes de urgencia
y costo se comporten como se espera en los casos límite."""
from app.dashboards import ahp


def test_pesos_ahp_suman_uno():
    w = ahp.compute_ahp_weights()
    assert abs((w.seguridad + w.urgencia + w.costo) - 1.0) < 1e-9


def test_matriz_de_comparacion_es_consistente():
    """Si esto falla, la matriz de juicio experto en PAIRWISE_MATRIX no es
    defendible como AHP y hay que revisarla antes de confiar en el ranking."""
    w = ahp.compute_ahp_weights()
    assert w.consistency_ratio < 0.10
    assert w.is_consistent is True


def test_seguridad_pesa_mas_que_costo():
    """Refleja el juicio de dominio documentado en ahp.py: en flotas de
    carga pesada, la seguridad debe pesar más que el costo puro."""
    w = ahp.compute_ahp_weights()
    assert w.seguridad > w.urgencia > w.costo


def test_urgencia_score_vencido_es_maxima():
    assert ahp.urgency_score(km_remaining=-500, urgency_threshold_km=1500) == 1.0
    assert ahp.urgency_score(km_remaining=0, urgency_threshold_km=1500) == 1.0


def test_urgencia_score_decae_con_kilometraje_restante():
    cercano = ahp.urgency_score(km_remaining=200, urgency_threshold_km=1500)
    lejano = ahp.urgency_score(km_remaining=1400, urgency_threshold_km=1500)
    muy_lejano = ahp.urgency_score(km_remaining=8000, urgency_threshold_km=1500)
    assert cercano > lejano > muy_lejano
    assert muy_lejano == 0.0


def test_urgencia_score_sin_kilometraje_programado_es_moderada():
    assert ahp.urgency_score(km_remaining=None, urgency_threshold_km=1500) == 0.3


def test_costo_score_usa_historico_real_cuando_existe():
    historico = {"frenos": 300.0, "aceite": 50.0}
    assert ahp.cost_score("frenos", historico) == 1.0  # el mas caro del set
    assert 0 < ahp.cost_score("aceite", historico) < 1.0


def test_costo_score_usa_respaldo_si_no_hay_historico():
    # sin historico, cae en fallback_costs; llantas es el mas caro del fallback
    assert ahp.cost_score("llantas", {}) == 1.0


def test_priority_score_prioriza_frenos_vencido_sobre_aceite_lejano():
    """Caso de uso real que motiva RF-20: un mantenimiento de frenos vencido
    debe rankear por encima de un cambio de aceite que todavía falta mucho,
    incluso si el aceite fuera (hipotéticamente) igual de urgente en km."""
    frenos_vencido = ahp.priority_score(
        seguridad=ahp.SAFETY_CRITICALITY["frenos"],
        urgencia=ahp.urgency_score(km_remaining=-100, urgency_threshold_km=1500),
        costo=ahp.cost_score("frenos", {}),
    )
    aceite_lejano = ahp.priority_score(
        seguridad=ahp.SAFETY_CRITICALITY["aceite"],
        urgencia=ahp.urgency_score(km_remaining=5000, urgency_threshold_km=1500),
        costo=ahp.cost_score("aceite", {}),
    )
    assert frenos_vencido > aceite_lejano
