"""RF-19: ranking de atención por vehículo (AHP de dos criterios) y la política
de alertas de RF-13 que comparte la escala de urgencia con RF-20."""
import pytest

from app.dashboards import ahp, alert_policy


def test_pesos_dos_criterios_siguen_a_a_mas_uno():
    assert ahp.weights_two_criteria(3).urgencia == pytest.approx(0.75)
    assert ahp.weights_two_criteria(3).costo == pytest.approx(0.25)
    assert ahp.weights_two_criteria(1).urgencia == pytest.approx(0.5)
    assert ahp.weights_two_criteria(9).urgencia == pytest.approx(0.9)
    assert ahp.weights_two_criteria(1 / 3).urgencia == pytest.approx(0.25)


def test_matriz_2x2_es_consistente_por_construccion():
    for a in (1, 2, 3, 5, 7, 9, 1 / 5):
        w = ahp.weights_two_criteria(a)
        assert w.consistency_ratio == 0.0
        assert w.urgencia + w.costo == pytest.approx(1.0)


@pytest.mark.parametrize("a", [0, -1, 10, 9.5, 0.05])
def test_razon_fuera_de_la_escala_de_saaty_se_rechaza(a):
    with pytest.raises(ValueError):
        ahp.weights_two_criteria(a)


VEHICULOS = [
    {"vehicle_id": "A", "plate": "AAA-001", "total_cost": 1000},
    {"vehicle_id": "B", "plate": "BBB-002", "total_cost": 100},
    {"vehicle_id": "C", "plate": "CCC-003", "total_cost": 0},
]
URGENCIA = {"A": 0.2, "B": 1.0}


def test_con_pesos_iguales_gana_el_vehiculo_caro_con_algo_de_urgencia():
    ranking = ahp.rank_vehicle_attention(VEHICULOS, URGENCIA, ahp.weights_two_criteria(1))
    assert [r.vehicle_id for r in ranking] == ["A", "B"]  # A: 0.6, B: 0.55


def test_al_subir_la_importancia_de_la_urgencia_gana_el_vencido():
    ranking = ahp.rank_vehicle_attention(VEHICULOS, URGENCIA, ahp.weights_two_criteria(9))
    assert [r.vehicle_id for r in ranking] == ["B", "A"]  # B: 0.91, A: 0.28


def test_un_vehiculo_sin_costo_ni_urgencia_no_aparece():
    ranking = ahp.rank_vehicle_attention(VEHICULOS, URGENCIA, ahp.weights_two_criteria(3))
    assert "C" not in [r.vehicle_id for r in ranking]


def test_limite_y_desempate_por_placa():
    igual = [{"vehicle_id": str(i), "plate": f"P-{9 - i}", "total_cost": 10} for i in range(4)]
    ranking = ahp.rank_vehicle_attention(igual, {}, ahp.weights_two_criteria(1), limit=2)
    assert [r.plate for r in ranking] == ["P-6", "P-7"]


def test_sin_vehiculos_devuelve_lista_vacia():
    assert ahp.rank_vehicle_attention([], {}, ahp.weights_two_criteria(3)) == []


def test_todos_con_costo_cero_no_divide_por_cero():
    ranking = ahp.rank_vehicle_attention(
        [{"vehicle_id": "A", "plate": "A", "total_cost": 0}], {"A": 0.5}, ahp.weights_two_criteria(3)
    )
    assert ranking[0].attention_score == pytest.approx(0.75 * 0.5)


@pytest.mark.parametrize(
    "km, esperado",
    [(None, "normal"), (-1, "vencido"), (0, "vencido"), (1, "proximo"), (1500, "proximo"), (1501, "normal")],
)
def test_clasificacion_de_urgencia_con_umbral_explicito(km, esperado):
    assert alert_policy.classify_urgency(km, proximo_km=1500) == esperado


def test_sin_umbral_explicito_se_usa_el_de_la_configuracion():
    umbral = ahp.CONFIG.urgencia.proximo_km
    assert alert_policy.classify_urgency(umbral) == "proximo"
    assert alert_policy.classify_urgency(umbral + 1) == "normal"
    assert alert_policy.classify_urgency(0) == "vencido"


def test_el_umbral_se_puede_pasar_explicito():
    assert alert_policy.classify_urgency(2500, proximo_km=3000) == "proximo"
    assert alert_policy.classify_urgency(2500, proximo_km=2000) == "normal"
