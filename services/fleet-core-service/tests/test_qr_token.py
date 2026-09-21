"""Pruebas unitarias de la credencial personal del portal de despacho (RF-18).
No requieren el stack levantado ni la base de datos."""
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.despacho import qr_token
from app.models.driver import Driver

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _conductor():
    return SimpleNamespace(
        qr_token_hash=None, qr_token_issued_at=None, qr_token_expires_at=None, qr_token_last_used_at=None
    )


def test_el_hash_es_sha256_hexadecimal():
    # Vector de prueba estándar de SHA-256.
    assert qr_token.hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert qr_token.hash_token("x") == hashlib.sha256(b"x").hexdigest()
    # Los caracteres no ASCII se codifican en UTF-8 (igual que convert_to(..., 'UTF8') en la migración).
    assert qr_token.hash_token("ñ") == hashlib.sha256("ñ".encode("utf-8")).hexdigest()


def test_emitir_guarda_solo_el_hash_y_fija_la_vigencia():
    c = _conductor()
    token = qr_token.issue(c, AHORA)
    assert len(token) == 32  # 24 bytes aleatorios en base64 url-safe
    assert c.qr_token_hash == qr_token.hash_token(token)
    assert token not in vars(c).values(), "el token en claro no debe quedar en el conductor"
    assert c.qr_token_issued_at == AHORA
    assert c.qr_token_expires_at == AHORA + timedelta(days=qr_token.TTL_DAYS)
    assert c.qr_token_last_used_at is None


def test_dos_emisiones_producen_tokens_distintos():
    assert qr_token.issue(_conductor()) != qr_token.issue(_conductor())


def test_el_token_emitido_es_valido_dentro_de_su_vigencia():
    c = _conductor()
    token = qr_token.issue(c, AHORA)
    assert qr_token.is_valid(c, token, AHORA)
    assert qr_token.is_valid(c, token, AHORA + timedelta(days=qr_token.TTL_DAYS) - timedelta(seconds=1))


def test_el_token_vence_exactamente_al_cumplirse_la_vigencia():
    c = _conductor()
    token = qr_token.issue(c, AHORA)
    limite = AHORA + timedelta(days=qr_token.TTL_DAYS)
    assert not qr_token.is_valid(c, token, limite)
    assert not qr_token.is_valid(c, token, limite + timedelta(days=1))


@pytest.mark.parametrize("presentado", [None, "", "token-falso", "x" * 32, "a" * 129])
def test_un_token_distinto_o_ausente_se_rechaza(presentado):
    c = _conductor()
    qr_token.issue(c, AHORA)
    assert not qr_token.is_valid(c, presentado, AHORA)


def test_un_token_de_otro_conductor_no_sirve():
    a, b = _conductor(), _conductor()
    token_a = qr_token.issue(a, AHORA)
    qr_token.issue(b, AHORA)
    assert not qr_token.is_valid(b, token_a, AHORA)


def test_rotar_invalida_el_token_anterior():
    c = _conductor()
    viejo = qr_token.issue(c, AHORA)
    nuevo = qr_token.issue(c, AHORA)
    assert not qr_token.is_valid(c, viejo, AHORA)
    assert qr_token.is_valid(c, nuevo, AHORA)


def test_revocar_deja_al_conductor_sin_credencial():
    c = _conductor()
    token = qr_token.issue(c, AHORA)
    qr_token.revoke(c)
    assert not qr_token.is_valid(c, token, AHORA)
    assert (c.qr_token_hash, c.qr_token_issued_at, c.qr_token_expires_at, c.qr_token_last_used_at) == (None,) * 4


def test_un_conductor_inexistente_se_rechaza_sin_error():
    assert not qr_token.is_valid(None, "cualquier-token", AHORA)


def test_conductor_sin_credencial_o_sin_vigencia_se_rechaza():
    sin_credencial = _conductor()
    assert not qr_token.is_valid(sin_credencial, "cualquier-token", AHORA)
    sin_vigencia = _conductor()
    token = qr_token.issue(sin_vigencia, AHORA)
    sin_vigencia.qr_token_expires_at = None
    assert not qr_token.is_valid(sin_vigencia, token, AHORA)


def test_la_comparacion_es_en_tiempo_constante_y_siempre_se_ejecuta(monkeypatch):
    llamadas = []
    real = qr_token.hmac.compare_digest

    def espia(a, b):
        llamadas.append((a, b))
        return real(a, b)

    monkeypatch.setattr(qr_token.hmac, "compare_digest", espia)
    c = _conductor()
    token = qr_token.issue(c, AHORA)
    qr_token.is_valid(c, token, AHORA)  # válido
    qr_token.is_valid(c, "otro", AHORA)  # falso
    qr_token.is_valid(None, "otro", AHORA)  # conductor inexistente
    qr_token.is_valid(_conductor(), "otro", AHORA)  # sin credencial
    assert len(llamadas) == 4, "cada caso debe pasar por compare_digest, sin atajos que filtren por tiempo"


def test_el_modelo_expone_has_qr():
    d = Driver()
    assert d.has_qr is False
    qr_token.issue(d, AHORA)
    assert d.has_qr is True
    qr_token.revoke(d)
    assert d.has_qr is False


def test_la_vigencia_por_defecto_es_de_180_dias(monkeypatch):
    monkeypatch.delenv("QR_TOKEN_TTL_DAYS", raising=False)
    assert qr_token.load_ttl_days() == 180


def test_la_vigencia_se_configura_por_entorno(monkeypatch):
    monkeypatch.setenv("QR_TOKEN_TTL_DAYS", "30")
    assert qr_token.load_ttl_days() == 30


@pytest.mark.parametrize("valor", ["abc", "", "0", "-5", "3651", "12.5"])
def test_una_vigencia_invalida_detiene_el_arranque(monkeypatch, valor):
    monkeypatch.setenv("QR_TOKEN_TTL_DAYS", valor)
    with pytest.raises(ValueError, match="QR_TOKEN_TTL_DAYS"):
        qr_token.load_ttl_days()
