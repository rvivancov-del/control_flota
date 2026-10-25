"""Análisis de sensibilidad del ranking AHP (RF-20), en la línea de Nugraha et
al. (2025): mover cada peso de criterio hasta +-30 % y comprobar que el orden
de prioridad se mantiene. No requiere el stack levantado.

Los umbrales son el estándar de robustez que se le exige al ranking: primer
lugar y top-3 intactos, y tau de Kendall >= 0.90 (concordancia fuerte). Si la
configuración de los expertos los incumple, estas pruebas lo revelan en vez de
dejar pasar un ranking frágil."""
import pytest

from app.dashboards import ahp, ahp_analysis as an

ITEMS = an.standard_item_set()


def test_kendall_identico_e_invertido():
    orden = ["a", "b", "c", "d"]
    assert an.kendall_tau(orden, orden) == 1.0
    assert an.kendall_tau(orden, orden[::-1]) == -1.0


def test_kendall_con_un_intercambio_adyacente():
    # 4 elementos = 6 pares; un intercambio adyacente rompe 1 par: (5 - 1) / 6
    assert an.kendall_tau(["a", "b", "c", "d"], ["a", "c", "b", "d"]) == pytest.approx(4 / 6)


def test_kendall_rechaza_conjuntos_distintos():
    with pytest.raises(ValueError):
        an.kendall_tau(["a", "b"], ["a", "c"])


def test_perturbar_un_peso_lo_sube_y_la_suma_sigue_en_uno():
    base = ahp.AHP_WEIGHTS
    p = an.perturb_weights(base, "costo", 0.3)
    assert p.costo > base.costo and p.seguridad < base.seguridad and p.urgencia < base.urgencia
    assert p.seguridad + p.urgencia + p.costo == pytest.approx(1.0)


def test_perturbar_con_delta_cero_no_cambia_nada():
    p = an.perturb_weights(ahp.AHP_WEIGHTS, "seguridad", 0.0)
    assert p.as_dict() == pytest.approx(ahp.AHP_WEIGHTS.as_dict())


def test_criterio_desconocido_se_rechaza():
    with pytest.raises(ValueError):
        an.perturb_weights(ahp.AHP_WEIGHTS, "kilometraje", 0.1)


def test_el_conjunto_estandar_cubre_tipos_y_estados():
    assert len(ITEMS) == 18 and len({i["id"] for i in ITEMS}) == 18


def test_el_ranking_es_determinista():
    assert an.rank_items(ITEMS, ahp.AHP_WEIGHTS) == an.rank_items(list(reversed(ITEMS)), ahp.AHP_WEIGHTS)


def test_un_vencido_de_maxima_criticidad_encabeza_el_ranking_base():
    """Con la criticidad de los expertos (varios tipos igual de críticos) el primer lugar no es un tipo fijo:
    es un mantenimiento vencido de criticidad máxima, y los empates se resuelven de forma determinista."""
    primero = an.rank_items(ITEMS, ahp.AHP_WEIGHTS)[0]
    item = next(i for i in ITEMS if i["id"] == primero)
    assert primero.endswith("-vencido")
    assert item["seguridad"] == max(i["seguridad"] for i in ITEMS)


def test_a_igual_puntaje_va_primero_el_mas_vencido_en_km():
    base = {"seguridad": 1.0, "urgencia": 1.0, "costo": 0.5}
    items = [{**base, "id": "a-poco-vencido", "km_remaining": -50},
             {**base, "id": "b-sin-km", "km_remaining": None},
             {**base, "id": "c-muy-vencido", "km_remaining": -900}]
    assert an.rank_items(items, ahp.AHP_WEIGHTS) == ["c-muy-vencido", "a-poco-vencido", "b-sin-km"]


@pytest.mark.parametrize("criterio", ahp.CRITERIA)
def test_el_primer_lugar_y_el_top3_resisten_cambios_de_hasta_30_por_ciento(criterio):
    rows = [r for r in an.sensitivity(ITEMS) if r.criterion == criterio]
    assert len(rows) == 6
    for r in rows:
        assert r.top1_same, f"cambia el 1.º al mover {criterio} {r.delta:+.0%}"
        assert r.top3_same, f"cambia el top-3 al mover {criterio} {r.delta:+.0%}"


def test_concordancia_fuerte_del_ranking_completo():
    for r in an.sensitivity(ITEMS):
        assert r.tau >= 0.90, f"{r.criterion} {r.delta:+.0%}: tau={r.tau:.3f}"


def test_el_informe_en_markdown_incluye_todas_las_perturbaciones():
    informe = an.markdown_report()
    assert informe.count("| seguridad |") == 6 and informe.count("| urgencia |") == 6 and informe.count("| costo |") == 6
    assert "τ mínimo global" in informe
