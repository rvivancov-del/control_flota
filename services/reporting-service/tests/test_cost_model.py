"""Pruebas unitarias del modelo de costos. Cada indicador se verifica contra un cálculo hecho
a mano con un caso de números redondos; el caso vive en la docstring de EJEMPLO para poder repetirlo
en papel. No requieren el stack."""
import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.dashboards import cost_model as cm
from app.dashboards import iva_config

D = Decimal

# EJEMPLO (30 días, 1 000 km):
#   Cv  = combustible 300 + peajes 50 + alimentación 40 + mantenimiento 110              = 500
#   Cf  = depreciación 150 + capital 50 + seguro 60 + impuestos 20 + otros 20 + personal 200 = 500
#   Ct  = 500 + 500 = 1 000;  R = 1 250
#   cv = 0,50  cf = 0,50  ct = 1,00  r = 1,25  u = 0,25   utilidad = 250   margen = 20 %
#   margen de contribución = 1 250 − 500 = 750;   LP = 1 250 / 200 = 6,25;   ROP = 250 / 200 = 125 %
ITEMS = {
    "combustible": D(300), "peaje": D(50), "alimentacion": D(40), "mantenimiento": D(110),
    "depreciacion": D(150), "capital": D(50), "seguro": D(60), "impuestos": D(20), "otros": D(20), "personal": D(200),
}
KM, REVENUE = 1000, D(1250)


def _eq(actual, esperado, places="0.0001"):
    assert actual is not None and actual.quantize(D(places)) == D(esperado), (actual, esperado)


# ------------------------------------------------------------------ Poliak: Ct = Cv + Cf y costos unitarios
def test_costo_variable_fijo_y_total():
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, KM)
    assert (ind.variable_cost, ind.fixed_cost, ind.total_cost) == (D(500), D(500), D(1000))
    assert ind.total_cost == ind.variable_cost + ind.fixed_cost  # ec. (1)


def test_costos_unitarios_por_kilometro():
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, KM)
    _eq(ind.cv_per_km, "0.5000"); _eq(ind.cf_per_km, "0.5000"); _eq(ind.ct_per_km, "1.0000")
    assert ind.ct_per_km == ind.cv_per_km + ind.cf_per_km


# ------------------------------------------------------------------ Zysińska: tarifa, utilidad y margen
def test_ingreso_utilidad_y_margen():
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, KM)
    _eq(ind.revenue_per_km, "1.2500"); _eq(ind.profit, "250.0000"); _eq(ind.profit_per_km, "0.2500"); _eq(ind.margin_pct, "20.0000")
    assert ind.profit_per_km == ind.revenue_per_km - ind.ct_per_km  # u = r − ct
    _eq(ind.revenue_coverage_pct, "100.0000")


def test_margen_de_contribucion_solo_usa_costos_variables():
    _eq(cm.compute_indicators(ITEMS, KM, REVENUE, KM).contribution_margin, "750.0000")


# ------------------------------------------------------------------ Zysińska: ocho categorías
def test_estructura_del_costo_en_ocho_categorias():
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, KM)
    esperado = {  # categoría: (monto, costo por km, % del total)
        "combustible": (300, "0.3", "30"), "reparaciones": (110, "0.11", "11"), "depreciacion": (150, "0.15", "15"),
        "capital": (50, "0.05", "5"), "personal": (240, "0.24", "24"),  # personal 200 + viáticos (alimentación) 40
        "seguros_impuestos": (80, "0.08", "8"), "peajes": (50, "0.05", "5"), "otros": (20, "0.02", "2"),
    }
    assert [c.key for c in ind.composition] == [k for k, _ in cm.CATEGORIES] and len(ind.composition) == 8
    for linea in ind.composition:
        monto, por_km, pct = esperado[linea.key]
        assert (linea.amount, linea.per_km.quantize(D("0.01")), linea.share_pct.quantize(D("0.01"))) == (D(monto), D(por_km).quantize(D("0.01")), D(pct).quantize(D("0.01")))
    assert sum(c.amount for c in ind.composition) == ind.total_cost
    assert sum(c.share_pct for c in ind.composition) == D(100)
    assert sum(c.per_km for c in ind.composition) == ind.ct_per_km


def test_el_combustible_pesa_sobre_el_total_real_y_no_sobre_cuatro_categorias():
    """El % de combustible se mide sobre el costo total, no sobre la suma de los cuatro rubros variables (60 %)."""
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, KM)
    combustible = next(c for c in ind.composition if c.key == "combustible")
    assert combustible.share_pct == D(30)
    assert D(300) / ind.variable_cost * 100 == D(60)  # lo que se mostraba antes


# ------------------------------------------------------------------ Kutac: LP y ROP
def test_productividad_laboral_y_retorno_sobre_costos_de_personal():
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, KM)
    assert ind.personnel_cost == D(200)  # solo sueldo y beneficios; los viáticos no cuentan
    _eq(ind.labour_productivity, "6.2500"); _eq(ind.return_on_personnel_cost_pct, "125.0000")


def test_sin_costos_de_personal_no_hay_productividad_laboral():
    sin_personal = {k: v for k, v in ITEMS.items() if k != "personal"}
    ind = cm.compute_indicators(sin_personal, KM, REVENUE, KM)
    assert ind.labour_productivity is None and ind.return_on_personnel_cost_pct is None and ind.personnel_cost == D(0)


# ------------------------------------------------------------------ vista sin costos fijos (rol operador o sin período)
def test_sin_costos_fijos_solo_se_calcula_lo_variable_y_no_se_finge_un_total():
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, KM, include_fixed=False)
    assert ind.fixed_included is False
    assert ind.variable_cost == D(500) and ind.cv_per_km == D("0.5")
    for campo in ("fixed_cost", "total_cost", "cf_per_km", "ct_per_km", "profit", "profit_per_km", "margin_pct",
                  "personnel_cost", "labour_productivity", "return_on_personnel_cost_pct"):
        assert getattr(ind, campo) is None, campo
    _eq(ind.contribution_margin, "750.0000")
    # la composición se reparte sobre lo que se ve (costos variables), y los rubros fijos no aparecen
    pct = {c.key: c.share_pct for c in ind.composition}
    assert pct["combustible"] == D(60) and pct["reparaciones"] == D(22) and pct["peajes"] == D(10) and pct["personal"] == D(8)
    assert pct["depreciacion"] == D(0) and sum(pct.values()) == D(100)


# ------------------------------------------------------------------ casos límite
def test_sin_kilometros_no_hay_indicadores_por_kilometro():
    ind = cm.compute_indicators(ITEMS, 0, REVENUE, 0)
    assert ind.cv_per_km is None and ind.ct_per_km is None and ind.revenue_per_km is None and ind.profit_per_km is None
    assert ind.total_cost == D(1000) and ind.profit == D(250) and ind.revenue_coverage_pct is None


def test_sin_ingresos_no_hay_utilidad_ni_margen_pero_si_costos():
    for ingreso in (None, D(0)):
        ind = cm.compute_indicators(ITEMS, KM, ingreso, 0)
        assert ind.revenue is None and ind.profit is None and ind.margin_pct is None and ind.contribution_margin is None
        assert ind.total_cost == D(1000) and ind.ct_per_km == D(1)


def test_cobertura_parcial_de_ingresos_se_informa():
    ind = cm.compute_indicators(ITEMS, KM, REVENUE, revenue_distance_km=600)
    _eq(ind.revenue_coverage_pct, "60.0000")


def test_una_perdida_da_utilidad_y_margen_negativos():
    ind = cm.compute_indicators(ITEMS, KM, D(800), KM)
    _eq(ind.profit, "-200.0000"); _eq(ind.margin_pct, "-25.0000"); _eq(ind.return_on_personnel_cost_pct, "-100.0000")


def test_sin_gastos_todo_es_cero_sin_dividir_por_cero():
    ind = cm.compute_indicators({}, 0, None, 0)
    assert ind.variable_cost == D(0) and ind.total_cost == D(0)
    assert all(c.share_pct is None and c.amount == 0 for c in ind.composition)


# ------------------------------------------------------------------ IVA bruto / neto
def test_modo_bruto_devuelve_los_montos_tal_cual():
    assert cm.apply_iva(ITEMS, iva_config.CONFIG.rates, "bruto") == ITEMS


def test_modo_neto_quita_el_iva_solo_de_los_rubros_con_tarifa():
    neto = cm.apply_iva(ITEMS, iva_config.CONFIG.rates, "neto")
    assert neto["peaje"] == D(50) and neto["personal"] == D(200)  # tarifa 0
    assert neto["combustible"].quantize(D("0.0001")) == D("260.8696")  # 300 / 1,15 (IVA del SRI, septiembre de 2026)
    assert neto["alimentacion"].quantize(D("0.0001")) == D("34.7826")  # 40 / 1,15
    assert neto["mantenimiento"].quantize(D("0.0001")) == D("95.6522")  # 110 / 1,15
    ind = cm.compute_indicators(neto, KM, REVENUE, KM)
    _eq(ind.variable_cost, "441.3043")  # 450/1,15 + 50
    assert ind.variable_cost < D(500)


def test_un_modo_desconocido_se_rechaza():
    with pytest.raises(ValueError, match="iva_mode"):
        cm.apply_iva(ITEMS, iva_config.CONFIG.rates, "gravado")


# ------------------------------------------------------------------ asignación del personal a vehículos
def test_el_personal_se_reparte_por_los_km_de_cada_conductor_y_se_conserva_el_total():
    personal = {"d1": D(1000), "d2": D(500), "d3": D(200)}
    km = {("d1", "v1"): 300, ("d1", "v2"): 100, ("d2", "v2"): 200}
    por_vehiculo, sin_asignar = cm.allocate_personnel(personal, km)
    assert por_vehiculo == {"v1": D(750), "v2": D(750)}  # d1: 1000 × 300/400 y 1000 × 100/400; d2: 500 al v2
    assert sin_asignar == D(200)  # d3 no condujo: no hay a qué vehículo cargarle su costo
    assert sum(por_vehiculo.values()) + sin_asignar == D(1700)


def test_un_conductor_con_costo_pero_sin_viajes_queda_sin_asignar_y_sin_viajes_ni_costos_no_hay_nada():
    assert cm.allocate_personnel({"d1": D(300)}, {}) == ({}, D(300))
    assert cm.allocate_personnel({}, {("d1", "v1"): 100}) == ({}, D(0))


def test_los_km_de_un_conductor_con_un_solo_vehiculo_cargan_todo_a_ese_vehiculo():
    assert cm.allocate_personnel({"d1": D(900)}, {("d1", "v9"): 5}) == ({"v9": D(900)}, D(0))


# ------------------------------------------------------------------ catálogo y tabla de trazabilidad
def test_cada_rubro_del_prototipo_pertenece_a_una_de_las_ocho_categorias():
    assert len(cm.CATEGORIES) == 8 and len({k for k, _ in cm.CATEGORIES}) == 8
    assert set(cm.ITEM_CATEGORY) == set(cm.ALL_ITEMS) and set(cm.ITEM_CATEGORY.values()) <= {k for k, _ in cm.CATEGORIES}
    assert set(cm.VARIABLE_ITEMS).isdisjoint(cm.FIXED_ITEMS)


def test_todas_las_categorias_reciben_al_menos_un_rubro():
    mapa = cm.category_map()
    assert [m["key"] for m in mapa] == [k for k, _ in cm.CATEGORIES]
    assert all(m["items"] for m in mapa)
    assert next(m for m in mapa if m["key"] == "personal")["behavior"] == "mixta"
    assert next(m for m in mapa if m["key"] == "combustible")["behavior"] == "variable"
    assert next(m for m in mapa if m["key"] == "depreciacion")["behavior"] == "fija"


def test_cada_indicador_declara_formula_y_fuente():
    assert len(cm.INDICATORS) >= 12
    for ind in cm.INDICATORS:
        assert ind.id and ind.name and ind.formula and ind.source and ind.where, ind


def test_sumar_rubros_de_varios_vehiculos():
    assert cm.sum_items([{"combustible": D(1), "peaje": D(2)}, {"combustible": D(10)}, {}]) == {"combustible": D(11), "peaje": D(2)}


# ------------------------------------------------------------------ configuración de IVA
DEFAULT_PATH = Path(iva_config.__file__).with_name("iva_config.json")


def _escribir(tmp_path, datos):
    path = tmp_path / "iva.json"
    path.write_text(json.dumps(datos), encoding="utf-8")
    return path


def test_la_configuracion_entregada_carga_y_declara_su_procedencia():
    cfg = iva_config.load_config()
    assert cfg.default_mode == "bruto" and cfg.estado == "pendiente_de_verificacion_contable"
    assert cfg.procedencia and cfg.rates["mantenimiento"] == D("0.15") and cfg.rates["combustible"] == D("0.15")
    assert set(cfg.rates) == set(cm.ALL_ITEMS)


@pytest.mark.parametrize(
    "mutar, mensaje",
    [
        (lambda d: d.update(modo_por_defecto="gravado"), "modo_por_defecto"),
        (lambda d: d.update(estado=""), "estado"),
        (lambda d: d.pop("procedencia"), "procedencia"),
        (lambda d: d["tarifas"].update(mantenimiento=0.3), "fuera de"),
        (lambda d: d["tarifas"].update(mantenimiento=-0.1), "fuera de"),
        (lambda d: d["tarifas"].update(mantenimiento="15%"), "número"),
        (lambda d: d["tarifas"].update(radiador=0.1), "desconocido"),
        (lambda d: d["tarifas"].pop("combustible"), "falta la tarifa"),
        (lambda d: d.update(tarifas=[0.15]), "objeto"),
    ],
)
def test_una_configuracion_de_iva_invalida_detiene_la_carga(tmp_path, mutar, mensaje):
    datos = copy.deepcopy(json.loads(DEFAULT_PATH.read_text(encoding="utf-8")))
    mutar(datos)
    with pytest.raises(ValueError, match=mensaje):
        iva_config.load_config(_escribir(tmp_path, datos))


def test_la_variable_de_entorno_reemplaza_la_configuracion(tmp_path, monkeypatch):
    datos = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    datos.update(estado="verificado_por_contador", modo_por_defecto="neto")
    datos["tarifas"]["combustible"] = 0.15
    monkeypatch.setenv("IVA_CONFIG_PATH", str(_escribir(tmp_path, datos)))
    cfg = iva_config.load_config()
    assert cfg.estado == "verificado_por_contador" and cfg.default_mode == "neto" and cfg.rates["combustible"] == D("0.15")
