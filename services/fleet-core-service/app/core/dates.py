"""Filtro por rango de fechas sobre columnas de fecha y hora con zona horaria (timestamptz).

Antes se filtraba con `func.date(Trip.departure_at) >= date_from`: aplicar una función a la columna impide
que PostgreSQL use un índice sobre ella y obliga a recorrer toda la tabla. Aquí el rango de días se
convierte en límites de instante, `columna >= inicio AND columna < fin`, que sí aprovecha un índice.

Los días se cuentan en UTC, como cuando la zona horaria de la sesión es UTC (que fija app/core/database.py):
un viaje que sale el 30 de septiembre a las 23:59:59 UTC pertenece al 30; a las 00:00:00 UTC del 1 de
octubre, al 1 de octubre."""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional


def utc_day_bounds(
    date_from: Optional[date], date_to: Optional[date]
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Límites [inicio, fin) en UTC del rango de días inclusivo [date_from, date_to]; None = sin cota."""
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from is not None else None
    end = None
    if date_to is not None:
        try:
            end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        except OverflowError:  # date.max no tiene día siguiente: sin cota superior
            end = None
    return start, end


def filter_utc_days(query, column, date_from: Optional[date], date_to: Optional[date]):
    """Acota `query` a las filas cuyo instante `column` cae en los días [date_from, date_to] (UTC), sin
    aplicar ninguna función a la columna."""
    start, end = utc_day_bounds(date_from, date_to)
    if start is not None:
        query = query.filter(column >= start)
    if end is not None:
        query = query.filter(column < end)
    return query
