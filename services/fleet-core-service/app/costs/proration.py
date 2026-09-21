"""Prorrateo por días de los costos fijos y de personal.

Un costo fijo se declara como un monto mensual o anual con su vigencia (desde/hasta). Para un
período de análisis [date_from, date_to] (ambos inclusive) se devenga:

    devengado = tarifa_diaria × días de la vigencia que caen dentro del período
    tarifa_diaria = monto_anual / 365                (período "anual")
                  = monto_mensual × 12 / 365         (período "mensual")

Se usa el año de 365 días también en años bisiestos: es una convención simple y reproducible a
mano, y la diferencia (0,27 %) queda por debajo de la incertidumbre de los propios montos.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

DAYS_PER_YEAR = Decimal(365)
MONTHS_PER_YEAR = Decimal(12)
_CENT = Decimal("0.01")


def overlap_days(valid_from: date, valid_to: Optional[date], date_from: date, date_to: date) -> int:
    """Días (inclusive) en que la vigencia [valid_from, valid_to] coincide con [date_from, date_to]."""
    start = max(valid_from, date_from)
    end = min(valid_to, date_to) if valid_to is not None else date_to
    return max(0, (end - start).days + 1)


def daily_rate(amount: Decimal, period: str) -> Decimal:
    if period == "anual":
        return amount / DAYS_PER_YEAR
    if period == "mensual":
        return amount * MONTHS_PER_YEAR / DAYS_PER_YEAR
    raise ValueError(f"período desconocido: {period!r}")


def accrued(
    amount: Decimal,
    period: str,
    valid_from: date,
    valid_to: Optional[date],
    date_from: date,
    date_to: date,
) -> Decimal:
    """Monto devengado en el período, sin redondear (se redondea al sumar por grupo)."""
    return daily_rate(Decimal(amount), period) * overlap_days(valid_from, valid_to, date_from, date_to)


def money(value: Decimal) -> Decimal:
    """Redondea a centavos, mitad hacia arriba."""
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)
