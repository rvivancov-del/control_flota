"""Pruebas unitarias de los costos fijos y de personal (Fase 3): prorrateo por días con cálculos
hechos a mano y validación de esquemas. No requieren el stack ni la base de datos."""
import importlib.util
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.costs import proration
from app.costs.schemas import FixedCostCreate, FixedCostUpdate, PersonnelCostCreate, PersonnelCostUpdate
from app.models.costs import FIXED_COST_CATEGORIES, PERIODS, PERSONNEL_CONCEPTS, FixedCost, PersonnelCost

MIGRATION = Path(__file__).resolve().parent.parent / "migrations" / "versions" / "e7c3b9d1a5f4_costos_fijos_y_de_personal.py"
D = Decimal


# ------------------------------------------------------------------ días de vigencia dentro del período
@pytest.mark.parametrize(
    "desde, hasta, p_desde, p_hasta, dias",
    [
        (date(2026, 1, 1), None, date(2026, 9, 1), date(2026, 9, 30), 30),  # vigente sin fin: todo el período
        (date(2026, 9, 10), None, date(2026, 9, 1), date(2026, 9, 30), 21),  # empieza a mitad de período (10..30)
        (date(2026, 1, 1), date(2026, 9, 15), date(2026, 9, 1), date(2026, 9, 30), 15),  # termina a mitad (1..15)
        (date(2026, 1, 1), date(2026, 3, 31), date(2026, 3, 15), date(2026, 4, 15), 17),  # 15..31 de marzo
        (date(2026, 9, 5), date(2026, 9, 5), date(2026, 9, 1), date(2026, 9, 30), 1),  # un solo día
        (date(2026, 1, 1), date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 30), 0),  # terminó antes
        (date(2026, 10, 1), None, date(2026, 9, 1), date(2026, 9, 30), 0),  # empieza después
        (date(2026, 9, 30), None, date(2026, 9, 1), date(2026, 9, 30), 1),  # empieza el último día
        (date(2026, 9, 1), date(2026, 9, 1), date(2026, 9, 1), date(2026, 9, 1), 1),  # período de un día
    ],
)
def test_dias_de_vigencia_dentro_del_periodo(desde, hasta, p_desde, p_hasta, dias):
    assert proration.overlap_days(desde, hasta, p_desde, p_hasta) == dias


# ------------------------------------------------------------------ tarifa diaria y devengo (cálculo a mano)
def test_tarifa_diaria_de_un_monto_anual():
    assert proration.daily_rate(D("3650"), "anual") == D("10")


def test_tarifa_diaria_de_un_monto_mensual_es_mensual_por_12_entre_365():
    # 730 × 12 / 365 = 24 exactos
    assert proration.daily_rate(D("730"), "mensual") == D("24")


def test_un_periodo_desconocido_se_rechaza():
    with pytest.raises(ValueError, match="período desconocido"):
        proration.daily_rate(D("1"), "semanal")


def test_devengo_anual_de_diez_dias():
    # 3650/365 = 10 por día × 10 días = 100
    assert proration.accrued(D("3650"), "anual", date(2026, 1, 1), None, date(2026, 9, 1), date(2026, 9, 10)) == D("100")


def test_devengo_mensual_de_un_mes_calendario_de_30_dias():
    # 300 × 12 / 365 = 9,863013698… por día × 30 días = 295,890410959… → 295,89 (no 300: se prorratea por días)
    valor = proration.accrued(D("300"), "mensual", date(2026, 1, 1), None, date(2026, 9, 1), date(2026, 9, 30))
    assert valor.quantize(D("0.000001")) == D("295.890411")
    assert proration.money(valor) == D("295.89")


def test_un_ano_completo_devenga_exactamente_el_monto_anual():
    assert proration.accrued(D("3650"), "anual", date(2026, 1, 1), None, date(2026, 1, 1), date(2026, 12, 31)) == D("3650")
    # 12 meses de 730 = 8 760 en el año; 365 días × 24 = 8 760
    assert proration.accrued(D("730"), "mensual", date(2026, 1, 1), None, date(2026, 1, 1), date(2026, 12, 31)) == D("8760")


def test_en_un_ano_bisiesto_se_mantiene_la_convencion_de_365_dias():
    # 366 días × 10 = 3 660 (0,27 % más): convención documentada en proration.py
    assert proration.accrued(D("3650"), "anual", date(2028, 1, 1), None, date(2028, 1, 1), date(2028, 12, 31)) == D("3660")


def test_sin_dias_de_vigencia_no_se_devenga_nada():
    assert proration.accrued(D("999"), "anual", date(2026, 10, 1), None, date(2026, 9, 1), date(2026, 9, 30)) == D("0")


def test_el_devengo_de_dos_tramos_consecutivos_suma_el_periodo_completo():
    """Un cambio de monto a mitad de período (p. ej. renovación del seguro) prorratea cada tramo por sus días."""
    p = (date(2026, 9, 1), date(2026, 9, 30))
    antes = proration.accrued(D("3650"), "anual", date(2026, 1, 1), date(2026, 9, 14), *p)  # 14 días × 10
    despues = proration.accrued(D("7300"), "anual", date(2026, 9, 15), None, *p)  # 16 días × 20
    assert (antes, despues) == (D("140"), D("320"))
    assert proration.money(antes + despues) == D("460.00")


def test_el_redondeo_es_a_centavos_mitad_hacia_arriba():
    assert proration.money(D("2.345")) == D("2.35")
    assert proration.money(D("2.344999")) == D("2.34")
    assert proration.money(D("100")) == D("100.00")


# ------------------------------------------------------------------ validación de esquemas
VEH, DRV = uuid.uuid4(), uuid.uuid4()
BASE_FIJO = dict(vehicle_id=VEH, category="seguro", amount=D("1200.00"), period="anual", valid_from=date(2026, 1, 1))
BASE_PERSONAL = dict(driver_id=DRV, concept="sueldo", amount=D("650.00"), valid_from=date(2026, 1, 1))


def test_un_costo_fijo_valido():
    c = FixedCostCreate(**BASE_FIJO)
    assert (c.category, c.period, c.valid_to) == ("seguro", "anual", None)


@pytest.mark.parametrize("campo, valor", [("category", "combustible"), ("category", ""), ("period", "semanal"), ("period", "Anual")])
def test_un_costo_fijo_rechaza_categorias_y_periodos_invalidos(campo, valor):
    with pytest.raises(ValidationError, match="debe ser uno de"):
        FixedCostCreate(**{**BASE_FIJO, campo: valor})


@pytest.mark.parametrize("monto", ["0", "-5", "0.00", "1234567890123.00", "10.005"])
def test_el_monto_debe_ser_positivo_y_caber_en_12_digitos_con_2_decimales(monto):
    with pytest.raises(ValidationError):
        FixedCostCreate(**{**BASE_FIJO, "amount": D(monto)})
    with pytest.raises(ValidationError):
        PersonnelCostCreate(**{**BASE_PERSONAL, "amount": D(monto)})


def test_la_vigencia_no_puede_terminar_antes_de_empezar():
    with pytest.raises(ValidationError, match="fecha final de la vigencia no puede ser anterior"):
        FixedCostCreate(**{**BASE_FIJO, "valid_to": date(2025, 12, 31)})
    with pytest.raises(ValidationError, match="fecha final de la vigencia no puede ser anterior"):
        PersonnelCostCreate(**{**BASE_PERSONAL, "valid_to": date(2025, 12, 31)})
    assert FixedCostCreate(**{**BASE_FIJO, "valid_to": date(2026, 1, 1)}).valid_to == date(2026, 1, 1)  # un día


def test_un_costo_de_personal_valido_y_sus_conceptos():
    assert PersonnelCostCreate(**BASE_PERSONAL).concept == "sueldo"
    for concepto in PERSONNEL_CONCEPTS:
        assert PersonnelCostCreate(**{**BASE_PERSONAL, "concept": concepto}).concept == concepto
    with pytest.raises(ValidationError, match="debe ser uno de"):
        PersonnelCostCreate(**{**BASE_PERSONAL, "concept": "bono"})


def test_las_ediciones_solo_validan_lo_que_se_envia():
    assert FixedCostUpdate(amount=D("1")).model_dump(exclude_unset=True) == {"amount": D("1")}
    assert PersonnelCostUpdate(notes="ajuste").model_dump(exclude_unset=True) == {"notes": "ajuste"}
    with pytest.raises(ValidationError):
        FixedCostUpdate(category="otra")
    with pytest.raises(ValidationError):
        PersonnelCostUpdate(amount=D("0"))


def test_las_notas_tienen_un_maximo_de_500_caracteres():
    with pytest.raises(ValidationError):
        FixedCostCreate(**{**BASE_FIJO, "notes": "x" * 501})


# ------------------------------------------------------------------ coherencia entre migración, modelos y catálogo
def test_la_migracion_y_los_modelos_coinciden():
    spec = importlib.util.spec_from_file_location("migracion_e7c3", MIGRATION)
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)
    codigo = MIGRATION.read_text(encoding="utf-8")
    for categoria in FIXED_COST_CATEGORIES:
        assert f"'{categoria}'" in codigo
    for concepto in PERSONNEL_CONCEPTS:
        assert f"'{concepto}'" in codigo
    for periodo in PERIODS:
        assert f"'{periodo}'" in codigo

    def checks(modelo):
        return {c.name for c in modelo.__table__.constraints if c.name and c.name.startswith("ck_")}

    assert checks(FixedCost) == {"ck_fixed_costs_amount_positive", "ck_fixed_costs_category", "ck_fixed_costs_period", "ck_fixed_costs_validity"}
    assert checks(PersonnelCost) == {"ck_personnel_costs_amount_positive", "ck_personnel_costs_concept", "ck_personnel_costs_validity"}
    for nombre in checks(FixedCost) | checks(PersonnelCost):
        assert nombre in codigo, f"la migración no crea la restricción {nombre}"
