"""Modelo de costos e indicadores: funciones puras, sin HTTP ni base de datos.

Cada indicador sale de una fórmula publicada; la lista INDICATORS al final es la fuente única de
la tabla "Indicador → fórmula → fuente → código" que usan la documentación y la interfaz.

- Poliak, Čulík, Huláková & Kováč (2025), ecs. (1)-(2): Ct = Cv + Cf y Cv = cv·M; costos unitarios
  cv, cf y ct por kilómetro. En su Tabla 3 el sueldo anual del conductor, la depreciación y el
  impuesto del vehículo figuran como costos fijos, y los peajes y el mantenimiento como variables.
  La tabla rotula también la energía eléctrica como costo fijo, pero el texto (sección 2) la trata
  como parte de los costos variables; el prototipo sigue el texto: el combustible es variable.
- Zysińska & Menes (2026): el costo de 1 vehículo-km se estructura en ocho categorías (Tabla 4);
  la tarifa (ingreso por km) y la utilidad por km = tarifa − costo (Tabla 3); margen = utilidad / tarifa.
- Kutac, Janovska, Kutac & Besta (2022): productividad laboral LP = S / PC (ec. 1) y retorno sobre
  costos de personal ROP = OP / PC (ec. 4). ROA y ROE (ecs. 2-3) exigen balance: fuera de alcance.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional

ZERO = Decimal("0")
HUNDRED = Decimal("100")

# ---------------------------------------------------------------------------- categorías
# Ocho categorías del costo de 1 vehículo-km (Zysińska & Menes, 2026, Tabla 4).
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("combustible", "Combustible y consumibles"),
    ("reparaciones", "Reparaciones, revisiones y llantas"),
    ("depreciacion", "Depreciación o pérdida de valor del rodante"),
    ("capital", "Otros costos de capital (leasing, crédito)"),
    ("personal", "Conductores: remuneración, viáticos y seguridad social"),
    ("seguros_impuestos", "Seguros del vehículo e impuestos sobre activos fijos"),
    ("peajes", "Peajes"),
    ("otros", "Otros costos de la actividad de transporte"),
)

# Rubros que registra el prototipo (llaves de los diccionarios de montos) y la categoría de
# Zysińska & Menes a la que corresponden.
ITEM_CATEGORY: dict[str, str] = {
    "combustible": "combustible",
    "mantenimiento": "reparaciones",
    "depreciacion": "depreciacion",
    "capital": "capital",
    "personal": "personal",  # sueldo y beneficios del conductor (tabla personnel_costs)
    "alimentacion": "personal",  # viáticos del conductor: los "gastos de viaje" de su categoría
    "seguro": "seguros_impuestos",
    "impuestos": "seguros_impuestos",
    "peaje": "peajes",
    "otros": "otros",
}
# Comportamiento frente al kilometraje (Poliak et al., 2025).
VARIABLE_ITEMS = ("combustible", "peaje", "alimentacion", "mantenimiento")
FIXED_ITEMS = ("depreciacion", "capital", "seguro", "impuestos", "otros", "personal")
ALL_ITEMS = VARIABLE_ITEMS + FIXED_ITEMS
CATEGORY_LABEL = dict(CATEGORIES)


# ---------------------------------------------------------------------------- redondeo
def q2(value: Optional[Decimal]) -> Optional[Decimal]:
    return None if value is None else Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q4(value: Optional[Decimal]) -> Optional[Decimal]:
    return None if value is None else Decimal(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _div(numerator: Decimal, denominator: Decimal) -> Optional[Decimal]:
    return numerator / denominator if denominator and denominator > 0 else None


# ---------------------------------------------------------------------------- IVA
def apply_iva(items: dict[str, Decimal], rates: dict[str, Decimal], mode: str) -> dict[str, Decimal]:
    """Modo 'bruto': los montos tal como se pagaron (con IVA). Modo 'neto': se les quita el IVA
    (monto / (1 + tarifa)), para empresas que lo recuperan como crédito tributario."""
    if mode == "bruto":
        return dict(items)
    if mode != "neto":
        raise ValueError(f"iva_mode debe ser 'bruto' o 'neto', se recibió {mode!r}")
    return {item: amount / (1 + rates.get(item, ZERO)) for item, amount in items.items()}


# ---------------------------------------------------------------------------- asignación de personal
def allocate_personnel(
    personnel_by_driver: dict[str, Decimal], km_by_driver_vehicle: dict[tuple[str, str], int]
) -> tuple[dict[str, Decimal], Decimal]:
    """Reparte el costo de personal de cada conductor entre los vehículos que condujo, en
    proporción a sus kilómetros con cada uno. Un conductor sin kilómetros en el período no tiene
    a qué vehículo cargarse: su costo queda 'sin asignar' (se suma al total de la flota, no a
    ningún vehículo). Devuelve (costo por vehículo, costo sin asignar)."""
    by_vehicle: dict[str, Decimal] = {}
    unallocated = ZERO
    total_km: dict[str, int] = {}
    for (driver, _), km in km_by_driver_vehicle.items():
        total_km[driver] = total_km.get(driver, 0) + km
    for driver, cost in personnel_by_driver.items():
        km_total = total_km.get(driver, 0)
        if km_total <= 0:
            unallocated += cost
            continue
        for (d, vehicle), km in km_by_driver_vehicle.items():
            if d == driver and km > 0:
                by_vehicle[vehicle] = by_vehicle.get(vehicle, ZERO) + cost * km / km_total
    return by_vehicle, unallocated


# ---------------------------------------------------------------------------- indicadores
@dataclass(frozen=True)
class CategoryLine:
    key: str
    label: str
    amount: Decimal
    per_km: Optional[Decimal]
    share_pct: Optional[Decimal]


@dataclass(frozen=True)
class Indicators:
    fixed_included: bool
    distance_km: int
    variable_cost: Decimal  # Cv
    fixed_cost: Optional[Decimal]  # Cf
    total_cost: Optional[Decimal]  # Ct
    cv_per_km: Optional[Decimal]
    cf_per_km: Optional[Decimal]
    ct_per_km: Optional[Decimal]
    revenue: Optional[Decimal]  # R (None si ningún viaje del período tiene ingreso)
    revenue_per_km: Optional[Decimal]
    revenue_coverage_pct: Optional[Decimal]  # % de los km con ingreso registrado
    profit: Optional[Decimal]  # U = R − Ct
    profit_per_km: Optional[Decimal]
    margin_pct: Optional[Decimal]  # U / R × 100
    contribution_margin: Optional[Decimal]  # R − Cv
    personnel_cost: Optional[Decimal]  # PC
    labour_productivity: Optional[Decimal]  # R / PC
    return_on_personnel_cost_pct: Optional[Decimal]  # U / PC × 100
    composition: tuple[CategoryLine, ...]


def by_category(items: dict[str, Decimal]) -> dict[str, Decimal]:
    """Suma los rubros del prototipo en las ocho categorías de Zysińska & Menes."""
    totals = {key: ZERO for key, _ in CATEGORIES}
    for item, amount in items.items():
        totals[ITEM_CATEGORY[item]] += amount
    return totals


def compute_indicators(
    items: dict[str, Decimal],
    distance_km: int,
    revenue: Optional[Decimal],
    revenue_distance_km: int = 0,
    include_fixed: bool = True,
) -> Indicators:
    """Calcula todos los indicadores de un vehículo, un conductor o la flota en un período.

    `items` trae los montos por rubro ya en el modo de IVA elegido. Con include_fixed=False (rol
    sin acceso a costos fijos, o período sin fechas) solo se consideran los rubros variables y no
    se calculan Cf, Ct ni lo que depende de ellos: no se muestra un total incompleto como si fuera el total."""
    variable = sum((items.get(i, ZERO) for i in VARIABLE_ITEMS), ZERO)
    fixed = sum((items.get(i, ZERO) for i in FIXED_ITEMS), ZERO) if include_fixed else None
    total = variable + fixed if fixed is not None else None
    personnel = items.get("personal", ZERO) if include_fixed else None
    R = revenue if revenue is not None and revenue > 0 else None

    profit = R - total if (R is not None and total is not None) else None
    ratios_pc = personnel if personnel is not None and personnel > 0 else None

    shown = items if include_fixed else {i: a for i, a in items.items() if i in VARIABLE_ITEMS}
    base_total = total if total is not None else variable
    lines = tuple(
        CategoryLine(
            key=key,
            label=CATEGORY_LABEL[key],
            amount=amount,
            per_km=_div(amount, Decimal(distance_km)),
            share_pct=(amount / base_total * HUNDRED) if base_total > 0 else None,
        )
        for key, amount in by_category(shown).items()
    )
    km = Decimal(distance_km)
    return Indicators(
        fixed_included=include_fixed,
        distance_km=distance_km,
        variable_cost=variable,
        fixed_cost=fixed,
        total_cost=total,
        cv_per_km=_div(variable, km),
        cf_per_km=_div(fixed, km) if fixed is not None else None,
        ct_per_km=_div(total, km) if total is not None else None,
        revenue=R,
        revenue_per_km=_div(R, km) if R is not None else None,
        revenue_coverage_pct=(Decimal(revenue_distance_km) / km * HUNDRED) if (R is not None and distance_km > 0) else None,
        profit=profit,
        profit_per_km=_div(profit, km) if profit is not None else None,
        margin_pct=(profit / R * HUNDRED) if (profit is not None and R is not None) else None,
        contribution_margin=(R - variable) if R is not None else None,
        personnel_cost=personnel,
        labour_productivity=_div(R, ratios_pc) if (R is not None and ratios_pc is not None) else None,
        return_on_personnel_cost_pct=(profit / ratios_pc * HUNDRED) if (profit is not None and ratios_pc is not None) else None,
        composition=lines,
    )


# ---------------------------------------------------------------------------- tabla de trazabilidad
@dataclass(frozen=True)
class IndicatorDoc:
    id: str
    name: str
    formula: str
    source: str
    where: str  # dónde se calcula en el código


INDICATORS: tuple[IndicatorDoc, ...] = (
    IndicatorDoc("Cv", "Costo variable", "combustible + peajes + alimentación + mantenimiento (por período)",
                 "Poliak et al. (2025), ec. (1)-(2)", "cost_model.compute_indicators"),
    IndicatorDoc("Cf", "Costo fijo", "depreciación + capital + seguro + impuestos + otros (prorrateados por días) + personal asignado",
                 "Poliak et al. (2025), Tabla 3; Zysińska & Menes (2026)", "fleet-core costs/proration.py; cost_model.allocate_personnel"),
    IndicatorDoc("Ct", "Costo total", "Cv + Cf", "Poliak et al. (2025), ec. (1)", "cost_model.compute_indicators"),
    IndicatorDoc("cv, cf, ct", "Costos unitarios", "C / M, con M = km de los viajes completados del período",
                 "Poliak et al. (2025)", "cost_model.compute_indicators"),
    IndicatorDoc("r", "Ingreso por km", "R / M (R = ingreso de los viajes completados)",
                 "Zysińska & Menes (2026), Tabla 3 (tarifa por vehículo-km)", "cost_model.compute_indicators"),
    IndicatorDoc("u", "Utilidad por km", "r − ct = (R − Ct) / M", "Zysińska & Menes (2026), Tabla 3", "cost_model.compute_indicators"),
    IndicatorDoc("m", "Margen", "(R − Ct) / R × 100", "Zysińska & Menes (2026), Tabla 3", "cost_model.compute_indicators"),
    IndicatorDoc("Estructura", "Costo por km en 8 categorías y su % del total", "monto de la categoría / M;  % = monto / Ct",
                 "Zysińska & Menes (2026), Tabla 4 y Fig. 1", "cost_model.by_category"),
    IndicatorDoc("LP", "Productividad laboral", "R / PC (PC = costos de personal)", "Kutac et al. (2022), ec. (1)", "cost_model.compute_indicators"),
    IndicatorDoc("ROP", "Retorno sobre costos de personal", "(R − Ct) / PC × 100", "Kutac et al. (2022), ec. (4)", "cost_model.compute_indicators"),
    IndicatorDoc("MC", "Margen de contribución", "R − Cv (visible sin costos fijos)", "Elaboración propia (no proviene de las fuentes)", "cost_model.compute_indicators"),
    IndicatorDoc("L/100 km", "Consumo de combustible", "litros / km × 100", "Milewski & Milewska (2023); Costagliola et al. (2025)", "service.build_dashboard_summary"),
    IndicatorDoc("IVA neto", "Monto sin IVA", "monto / (1 + tarifa del rubro); modo 'bruto' por defecto",
                 "LRTI Art. 56 y circular del SRI (tarifas provisionales, ver iva_config.json)", "cost_model.apply_iva"),
)


def category_map() -> list[dict]:
    """Correspondencia categoría de Zysińska & Menes ↔ rubros del prototipo (para la interfaz y la documentación)."""
    result = []
    for key, label in CATEGORIES:
        items = [i for i in ALL_ITEMS if ITEM_CATEGORY[i] == key]
        result.append({"key": key, "label": label, "items": items,
                       "behavior": "variable" if all(i in VARIABLE_ITEMS for i in items) else ("fija" if all(i in FIXED_ITEMS for i in items) else "mixta")})
    return result


def sum_items(dicts: Iterable[dict[str, Decimal]]) -> dict[str, Decimal]:
    """Suma varios diccionarios de montos por rubro (vehículos de un alcance → flota)."""
    total: dict[str, Decimal] = {}
    for d in dicts:
        for item, amount in d.items():
            total[item] = total.get(item, ZERO) + amount
    return total
