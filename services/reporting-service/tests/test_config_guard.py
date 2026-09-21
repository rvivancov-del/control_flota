"""Pruebas unitarias de la guardia de configuración (RNF-02): sin base de datos ni stack.
El mismo archivo de pruebas vive en los tres servicios porque config_guard.py es idéntico."""
import pytest

from app.core import config_guard

SECRETO_LARGO = "x" * 40
CLAVE_DB = "una-clave-de-base-de-datos"


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for nombre in ("APP_ENV", "JWT_SECRET_KEY", "POSTGRES_PASSWORD", "ADMIN_INITIAL_PASSWORD"):
        monkeypatch.delenv(nombre, raising=False)


@pytest.mark.parametrize("modo", ["development", "dev", "local", "test", "Development", " DEV "])
def test_en_desarrollo_se_aceptan_los_secretos_por_defecto(monkeypatch, modo):
    monkeypatch.setenv("APP_ENV", modo)
    assert config_guard.is_development()
    assert config_guard.insecure_settings({"ADMIN_INITIAL_PASSWORD": "Admin1234"}) == []
    config_guard.assert_secure_configuration("svc")  # no lanza


def test_si_falta_app_env_se_asume_produccion(monkeypatch):
    assert config_guard.environment() == "production" and not config_guard.is_development()
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY tiene el valor por defecto"):
        config_guard.assert_secure_configuration("svc")


@pytest.mark.parametrize("modo", ["production", "prod", "staging", "cualquier-otra-cosa"])
def test_fuera_de_desarrollo_los_secretos_por_defecto_detienen_el_arranque(monkeypatch, modo):
    monkeypatch.setenv("APP_ENV", modo)
    problemas = config_guard.insecure_settings()
    assert any("JWT_SECRET_KEY" in p for p in problemas) and any("POSTGRES_PASSWORD" in p for p in problemas)
    with pytest.raises(RuntimeError) as error:
        config_guard.assert_secure_configuration("mi-servicio")
    assert "mi-servicio" in str(error.value) and modo in str(error.value)


def test_una_configuracion_real_en_produccion_es_aceptada(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", SECRETO_LARGO)
    monkeypatch.setenv("POSTGRES_PASSWORD", CLAVE_DB)
    assert config_guard.insecure_settings() == []
    config_guard.assert_secure_configuration("svc")


def test_una_clave_jwt_corta_se_rechaza(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * (config_guard.MIN_JWT_SECRET_LENGTH - 1))
    monkeypatch.setenv("POSTGRES_PASSWORD", CLAVE_DB)
    assert config_guard.insecure_settings() == [
        f"JWT_SECRET_KEY es demasiado corta (mínimo {config_guard.MIN_JWT_SECRET_LENGTH} caracteres)"
    ]
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * config_guard.MIN_JWT_SECRET_LENGTH)
    assert config_guard.insecure_settings() == []


def test_el_servicio_sin_base_de_datos_no_exige_su_contrasena(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", SECRETO_LARGO)
    assert any("POSTGRES_PASSWORD" in p for p in config_guard.insecure_settings())
    assert config_guard.insecure_settings(uses_database=False) == []
    config_guard.assert_secure_configuration("reporting", uses_database=False)


def test_los_secretos_adicionales_tambien_se_verifican(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", SECRETO_LARGO)
    monkeypatch.setenv("POSTGRES_PASSWORD", CLAVE_DB)
    extra = {"ADMIN_INITIAL_PASSWORD": "Admin1234"}
    assert config_guard.insecure_settings(extra) == ["ADMIN_INITIAL_PASSWORD tiene el valor por defecto de desarrollo"]
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", "otra-clave-inicial-9")
    assert config_guard.insecure_settings(extra) == []


def test_el_mensaje_lista_todos_los_problemas_a_la_vez(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError) as error:
        config_guard.assert_secure_configuration("svc")
    mensaje = str(error.value)
    assert "JWT_SECRET_KEY" in mensaje and "POSTGRES_PASSWORD" in mensaje and "APP_ENV=development" in mensaje
