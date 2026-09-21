"""Pruebas unitarias del bloqueo temporal de cuentas (RNF-03): sin base de datos ni stack."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core import lockout

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _usuario():
    return SimpleNamespace(failed_login_attempts=0, locked_until=None)


def test_los_valores_por_defecto_son_5_intentos_y_15_minutos():
    assert lockout.MAX_FAILED_ATTEMPTS == 5
    assert lockout.LOCKOUT_MINUTES == 15


def test_los_primeros_fallos_solo_se_cuentan():
    u = _usuario()
    for i in range(1, lockout.MAX_FAILED_ATTEMPTS):
        assert lockout.register_failure(u, AHORA) is False
        assert u.failed_login_attempts == i
    assert u.locked_until is None and not lockout.is_locked(u, AHORA)


def test_el_ultimo_fallo_permitido_bloquea_por_el_tiempo_configurado():
    u = _usuario()
    resultados = [lockout.register_failure(u, AHORA) for _ in range(lockout.MAX_FAILED_ATTEMPTS)]
    assert resultados == [False] * (lockout.MAX_FAILED_ATTEMPTS - 1) + [True]
    assert u.locked_until == AHORA + timedelta(minutes=lockout.LOCKOUT_MINUTES)
    assert u.failed_login_attempts == 0, "el contador vuelve a cero al bloquear"


def test_el_bloqueo_termina_exactamente_al_vencer():
    u = _usuario()
    for _ in range(lockout.MAX_FAILED_ATTEMPTS):
        lockout.register_failure(u, AHORA)
    fin = u.locked_until
    assert lockout.is_locked(u, AHORA)
    assert lockout.is_locked(u, fin - timedelta(seconds=1))
    assert not lockout.is_locked(u, fin)
    assert not lockout.is_locked(u, fin + timedelta(minutes=1))


def test_al_vencer_el_bloqueo_hay_un_intento_nuevo_completo():
    u = _usuario()
    for _ in range(lockout.MAX_FAILED_ATTEMPTS):
        lockout.register_failure(u, AHORA)
    despues = u.locked_until + timedelta(seconds=1)
    assert lockout.register_failure(u, despues) is False, "un solo fallo tras el bloqueo no vuelve a bloquear"
    assert u.failed_login_attempts == 1


def test_un_bloqueo_repetido_se_extiende_desde_el_nuevo_momento():
    u = _usuario()
    for _ in range(lockout.MAX_FAILED_ATTEMPTS):
        lockout.register_failure(u, AHORA)
    mas_tarde = AHORA + timedelta(hours=2)
    for _ in range(lockout.MAX_FAILED_ATTEMPTS):
        lockout.register_failure(u, mas_tarde)
    assert u.locked_until == mas_tarde + timedelta(minutes=lockout.LOCKOUT_MINUTES)


def test_limpiar_borra_el_contador_y_el_bloqueo():
    u = _usuario()
    for _ in range(lockout.MAX_FAILED_ATTEMPTS):
        lockout.register_failure(u, AHORA)
    lockout.register_failure(u, AHORA + timedelta(hours=1))
    lockout.clear(u)
    assert (u.failed_login_attempts, u.locked_until) == (0, None)


@pytest.mark.parametrize("valor", ["abc", "", "2", "21", "1.5"])
def test_una_configuracion_invalida_de_intentos_detiene_el_arranque(valor, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_FAILED_ATTEMPTS", valor)
    with pytest.raises(ValueError, match="LOGIN_MAX_FAILED_ATTEMPTS"):
        lockout._env_int("LOGIN_MAX_FAILED_ATTEMPTS", 5, 3, 20)


@pytest.mark.parametrize("valor", ["abc", "0", "1441"])
def test_una_configuracion_invalida_de_minutos_detiene_el_arranque(valor, monkeypatch):
    monkeypatch.setenv("LOGIN_LOCKOUT_MINUTES", valor)
    with pytest.raises(ValueError, match="LOGIN_LOCKOUT_MINUTES"):
        lockout._env_int("LOGIN_LOCKOUT_MINUTES", 15, 1, 1440)


def test_una_configuracion_valida_se_lee_del_entorno(monkeypatch):
    monkeypatch.setenv("LOGIN_LOCKOUT_MINUTES", "30")
    assert lockout._env_int("LOGIN_LOCKOUT_MINUTES", 15, 1, 1440) == 30
