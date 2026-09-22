"""Pruebas del filtro por rango de fechas sobre instantes (app/core/dates.py): debe seleccionar exactamente
las mismas filas que el `date(columna) BETWEEN ...` anterior, pero sin aplicar una función a la columna
(lo que impedía usar un índice). No requieren el stack ni la base de datos."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core import database
from app.core.dates import filter_utc_days, utc_day_bounds
from app.models.trip import Trip

UTC = timezone.utc


def test_un_rango_de_dias_es_un_intervalo_semiabierto_en_utc():
    inicio, fin = utc_day_bounds(date(2026, 9, 1), date(2026, 9, 30))
    assert inicio == datetime(2026, 9, 1, tzinfo=UTC)
    assert fin == datetime(2026, 10, 1, tzinfo=UTC)  # el 30 completo entra; el 1 de octubre a las 00:00 no


def test_un_solo_dia_abarca_veinticuatro_horas():
    inicio, fin = utc_day_bounds(date(2026, 9, 10), date(2026, 9, 10))
    assert fin - inicio == timedelta(hours=24)


def test_sin_cotas_no_filtra():
    assert utc_day_bounds(None, None) == (None, None)
    assert utc_day_bounds(date(2026, 9, 1), None) == (datetime(2026, 9, 1, tzinfo=UTC), None)
    assert utc_day_bounds(None, date(2026, 9, 1)) == (None, datetime(2026, 9, 2, tzinfo=UTC))


def test_la_ultima_fecha_posible_no_desborda():
    assert utc_day_bounds(None, date.max) == (None, None)


def test_pasa_de_un_ano_y_de_un_mes_de_febrero_bisiesto():
    assert utc_day_bounds(None, date(2027, 12, 31))[1] == datetime(2028, 1, 1, tzinfo=UTC)
    assert utc_day_bounds(None, date(2028, 2, 28))[1] == datetime(2028, 2, 29, tzinfo=UTC)
    assert utc_day_bounds(None, date(2028, 2, 29))[1] == datetime(2028, 3, 1, tzinfo=UTC)


@pytest.mark.parametrize("desde,hasta", [
    (date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 9, 15), date(2026, 9, 15)), (date(2026, 12, 31), date(2027, 1, 2)),
])
def test_equivale_al_filtro_por_fecha_de_cada_instante(desde, hasta):
    """Para instantes alrededor de cada medianoche (± 1 µs, ± 1 s, mediodía) el intervalo y la comparación
    por fecha UTC deciden lo mismo: es la equivalencia que justifica cambiar el predicado."""
    inicio, fin = utc_day_bounds(desde, hasta)
    base = datetime.combine(desde - timedelta(days=2), datetime.min.time(), tzinfo=UTC)
    comprobados = 0
    for dia in range(0, (hasta - desde).days + 6):
        medianoche = base + timedelta(days=dia)
        for delta in (timedelta(microseconds=-1), timedelta(0), timedelta(microseconds=1), timedelta(seconds=-1),
                      timedelta(hours=12), timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)):
            instante = medianoche + delta
            en_intervalo = inicio <= instante < fin
            por_fecha = desde <= instante.astimezone(UTC).date() <= hasta
            assert en_intervalo == por_fecha, instante
            comprobados += 1
    assert comprobados > 30


def test_el_predicado_no_aplica_ninguna_funcion_a_la_columna():
    """La razón del cambio: con `date(departure_at)` PostgreSQL no puede usar un índice sobre departure_at."""
    consulta = filter_utc_days(Session().query(Trip), Trip.departure_at, date(2026, 9, 1), date(2026, 9, 30))
    sql = str(consulta.statement.compile(dialect=postgresql.dialect())).lower()
    assert "date(" not in sql and "cast(" not in sql
    assert "trips.departure_at >=" in sql and "trips.departure_at <" in sql


def test_la_sesion_de_la_base_de_datos_cuenta_los_dias_en_utc():
    """Si la zona de la sesión no fuera UTC, `date(columna)` de otras consultas y estos límites discreparían."""
    assert "-ctimezone=UTC" in database.CONNECTION_OPTIONS and "-csearch_path=" in database.CONNECTION_OPTIONS
