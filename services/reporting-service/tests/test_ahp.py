"""Pruebas unitarias del método AHP (RF-20) — no requieren el stack levantado.
Validan la matemática de app/dashboards/ahp.py con la configuración que se
entrega (ahp_config.json) y con configuraciones explícitas para los casos límite.

Los valores esperados de los pesos y del CR se calcularon aparte (Python
independiente y Excel, ver 07_MATRICES_DE_ANALISIS/ahp_juicios_expertos.xlsx)
para la matriz [[1,3,5],[1/3,1,3],[1/5,1/3,1]]."""
import pytest

from app.dashboards import ahp

MATRIZ_PREVIA = [[1.0, 3.0, 5.0], [1 / 3, 1.0, 3.0], [1 / 5, 1 / 3, 1.0]]
COSTO_MAYOR = ahp.CostConfig(
    ahp.DIR_MAYOR, {"llantas": 275.0, "frenos": 150.0, "bocines": 120.0, "aceite": 55.0, "filtros": 40.0, "otro": 100.0}
)


def test_pesos_ahp_suman_uno():
    w = ahp.compute_ahp_weights()
    assert abs((w.seguridad + w.urgencia + w.costo) - 1.0) < 1e-9


def test_pesos_y_cr_coinciden_con_el_calculo_independiente():
    w = ahp.compute_ahp_weights(MATRIZ_PREVIA)
    assert w.seguridad == pytest.approx(0.633346, abs=1e-5)
    assert w.urgencia == pytest.approx(0.260498, abs=1e-5)
    assert w.costo == pytest.approx(0.106156, abs=1e-5)
    assert w.consistency_ratio == pytest.approx(0.033375, abs=1e-5)


def test_matriz_de_comparacion_es_consistente():
    """Si esto falla, la matriz configurada no es defendible como AHP."""
    w = ahp.compute_ahp_weights()
    assert w.consistency_ratio < 0.10
    assert w.is_consistent is True


def test_los_pesos_respetan_las_comparaciones_de_la_matriz():
    """Método, no juicio: si el juicio dice que A pesa más que B, el peso de A
    debe ser mayor. Vale para cualquier matriz consistente (también la de expertos)."""
    w = ahp.compute_ahp_weights().as_dict()
    m = ahp.CONFIG.matrix
    for i, ci in enumerate(ahp.CRITERIA):
        for j, cj in enumerate(ahp.CRITERIA):
            if m[i][j] > 1:
                assert w[ci] > w[cj]


PROXIMO = 1500  # umbral 'próximo' de fleet-core (RF-13) que las pruebas pasan explícito


def test_urgencia_vencido_es_maxima():
    assert ahp.urgency_score(-500, PROXIMO) == 1.0
    assert ahp.urgency_score(0, PROXIMO) == 1.0


def test_urgencia_decae_con_kilometraje_restante():
    cercano = ahp.urgency_score(200, PROXIMO)
    lejano = ahp.urgency_score(1400, PROXIMO)
    muy_lejano = ahp.urgency_score(int(PROXIMO * ahp.CONFIG.urgencia.sin_urgencia_multiplo) + 2000, PROXIMO)
    assert cercano > lejano > muy_lejano
    assert muy_lejano == 0.0


def test_urgencia_sin_kilometraje_programado_usa_el_puntaje_configurado():
    assert ahp.urgency_score(None, PROXIMO) == ahp.CONFIG.urgencia.puntaje_sin_kilometraje


def test_urgencia_en_el_umbral_proximo_vale_el_puntaje_configurado():
    u = ahp.CONFIG.urgencia
    assert ahp.urgency_score(PROXIMO, PROXIMO) == pytest.approx(u.puntaje_en_proximo)
    assert ahp.urgency_score(int(PROXIMO * u.sin_urgencia_multiplo), PROXIMO) == pytest.approx(0.0, abs=1e-9)


def test_el_umbral_proximo_escala_la_curva():
    """Con otro umbral (política de fleet-core) la curva se desplaza en proporción."""
    u = ahp.CONFIG.urgencia
    assert ahp.urgency_score(3000, 3000) == pytest.approx(u.puntaje_en_proximo)
    assert ahp.urgency_score(500, 1000) == pytest.approx(ahp.urgency_score(1500, 3000))


def _urgencia_implementacion_previa(km, umbral=1500):
    """Fórmula que estaba escrita a mano en ahp.py antes de externalizar la configuración."""
    if km is None:
        return 0.3
    if km <= 0:
        return 1.0
    if km <= umbral:
        return 1.0 - 0.5 * (km / umbral)
    return max(0.0, 0.5 - 0.5 * ((km - umbral) / (umbral * 3)))


@pytest.mark.parametrize("umbral", [1000, 1500, 3000])
def test_externalizar_la_configuracion_no_cambio_la_curva_de_urgencia(umbral):
    """Regresión: con la configuración provisional (múltiplo 4, 0.5 en 'próximo',
    0.3 sin kilometraje) el puntaje es idéntico al de la implementación previa."""
    cfg = ahp.UrgencyConfig(sin_urgencia_multiplo=4, puntaje_en_proximo=0.5, puntaje_sin_kilometraje=0.3)
    for km in [None, *range(-500, 9000, 25)]:
        assert ahp.urgency_score(km, umbral, cfg) == pytest.approx(_urgencia_implementacion_previa(km, umbral), abs=1e-12)


def test_costo_usa_historico_real_cuando_existe():
    historico = {"frenos": 300.0, "aceite": 50.0}
    assert ahp.cost_score("frenos", historico, COSTO_MAYOR) == 1.0  # el más caro del conjunto
    assert 0 < ahp.cost_score("aceite", historico, COSTO_MAYOR) < 1.0


def test_costo_usa_respaldo_si_no_hay_historico():
    # sin histórico cae en respaldo_usd; llantas es el más caro del respaldo
    assert ahp.cost_score("llantas", {}, COSTO_MAYOR) == 1.0


def test_costo_direccion_menor_invierte_el_puntaje():
    menor = ahp.CostConfig(ahp.DIR_MENOR, COSTO_MAYOR.respaldo_usd)
    assert ahp.cost_score("llantas", {}, menor) == pytest.approx(0.0)
    assert ahp.cost_score("filtros", {}, menor) == pytest.approx(1.0 - 40 / 275)


def test_costo_indiferente_no_altera_el_orden():
    neutro = ahp.CostConfig(ahp.DIR_INDIFERENTE, COSTO_MAYOR.respaldo_usd)
    assert ahp.cost_score("llantas", {}, neutro) == ahp.cost_score("filtros", {}, neutro) == 0.5


def test_tipo_desconocido_cae_en_otro():
    assert ahp.safety_score("radiador") == ahp.CONFIG.criticidad_seguridad["otro"]
    assert ahp.cost_score("radiador", {}, COSTO_MAYOR) == pytest.approx(100 / 275)


def test_priority_score_prioriza_frenos_vencido_sobre_aceite_lejano():
    """Caso de uso real que motiva RF-20: un mantenimiento de frenos vencido
    debe rankear por encima de un cambio de aceite que todavía falta mucho."""
    frenos_vencido = ahp.priority_score(ahp.safety_score("frenos"), ahp.urgency_score(-100, PROXIMO), ahp.cost_score("frenos", {}))
    aceite_lejano = ahp.priority_score(ahp.safety_score("aceite"), ahp.urgency_score(5000, PROXIMO), ahp.cost_score("aceite", {}))
    assert frenos_vencido > aceite_lejano
