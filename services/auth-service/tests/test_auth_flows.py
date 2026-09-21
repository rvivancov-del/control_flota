"""Pruebas unitarias del inicio de sesión, el bloqueo temporal, el cambio de contraseña y la matriz
de roles de auth-service (RF-02, RF-03, RNF-02, RNF-03). No requieren el stack ni PostgreSQL: la
sesión de SQLAlchemy se sustituye por un doble mínimo que devuelve un usuario en memoria; los JWT,
el hash bcrypt, el bloqueo y las dependencias de autorización son los reales."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jose import jwt

from app.core import lockout, security
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app

CLAVE = "Clave1234"
CLAVE_NUEVA = "OtraClave5678"
HASH = hash_password(CLAVE)
MENSAJE_INVALIDO = "Usuario o contraseña inválidos, o cuenta inactiva o bloqueada temporalmente."


def _usuario(role="operador", **cambios):
    datos = dict(
        id=uuid.uuid4(), username="usuario", full_name="Usuario de prueba", password_hash=HASH, is_active=True,
        failed_login_attempts=0, locked_until=None, must_change_password=False, password_changed_at=None,
        created_at=None, role=SimpleNamespace(id=uuid.uuid4(), name=role),
    )
    datos.update(cambios)
    return SimpleNamespace(**datos)


class _Sesion:
    """Doble mínimo de la sesión: query(...).filter(...).first() y get(...) devuelven el usuario dado;
    cualquier otro uso (joins, conteos, listados) falla, como si no hubiera base de datos."""

    def __init__(self, usuario=None):
        self.usuario, self.commits = usuario, 0

    def query(self, *_):
        return self

    def filter(self, *_):
        return self

    def first(self):
        return self.usuario

    def get(self, *_):
        return self.usuario

    def commit(self):
        self.commits += 1

    def refresh(self, _):
        pass

    def __getattr__(self, nombre):
        raise RuntimeError(f"sin base de datos en las pruebas unitarias ({nombre})")


@pytest.fixture()
def cliente():
    """Devuelve una función que arma un cliente con la sesión indicada."""

    def _armar(usuario=None):
        sesion = _Sesion(usuario)
        app.dependency_overrides[get_db] = lambda: sesion
        return TestClient(app, raise_server_exceptions=False), sesion

    yield _armar
    app.dependency_overrides.clear()


def _login(c, clave=CLAVE, usuario="usuario"):
    return c.post("/login", json={"username": usuario, "password": clave})


def _claims(token):
    return jwt.decode(token, security.JWT_SECRET_KEY, algorithms=[security.JWT_ALGORITHM])


def _auth(usuario):
    token = create_access_token(str(usuario.id), usuario.role.name, usuario.must_change_password)
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ login
def test_login_correcto_emite_un_token_sin_marca_de_cambio(cliente):
    u = _usuario(failed_login_attempts=3)
    c, sesion = cliente(u)
    r = _login(c)
    assert r.status_code == 200
    assert "mcp" not in _claims(r.json()["access_token"])
    assert r.json()["user"]["must_change_password"] is False
    assert u.failed_login_attempts == 0 and sesion.commits == 1


def test_login_de_quien_debe_cambiar_la_clave_lleva_la_marca_en_el_token(cliente):
    c, _ = cliente(_usuario(must_change_password=True))
    r = _login(c)
    assert r.status_code == 200
    assert _claims(r.json()["access_token"])["mcp"] is True
    assert r.json()["user"]["must_change_password"] is True


def test_un_fallo_cuenta_un_intento(cliente):
    u = _usuario()
    c, sesion = cliente(u)
    r = _login(c, "incorrecta1")
    assert r.status_code == 401 and r.json()["detail"] == MENSAJE_INVALIDO
    assert u.failed_login_attempts == 1 and u.locked_until is None and sesion.commits == 1


def test_el_quinto_fallo_bloquea_y_ni_la_clave_correcta_entra_durante_el_bloqueo(cliente):
    u = _usuario()
    c, _ = cliente(u)
    for _ in range(lockout.MAX_FAILED_ATTEMPTS):
        assert _login(c, "incorrecta1").status_code == 401
    ahora = datetime.now(timezone.utc)
    assert u.locked_until is not None and u.is_active, "queda bloqueada, no desactivada"
    assert ahora + timedelta(minutes=lockout.LOCKOUT_MINUTES - 1) < u.locked_until <= ahora + timedelta(minutes=lockout.LOCKOUT_MINUTES)
    correcto = _login(c)
    assert correcto.status_code == 401 and correcto.json()["detail"] == MENSAJE_INVALIDO


def test_al_vencer_el_bloqueo_la_cuenta_vuelve_a_entrar_sola(cliente):
    u = _usuario(locked_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    c, _ = cliente(u)
    assert _login(c).status_code == 200
    assert u.locked_until is None and u.failed_login_attempts == 0


def test_todos_los_rechazos_de_login_responden_igual(cliente):
    casos = {
        "usuario inexistente": _login(cliente(None)[0]),
        "clave incorrecta": _login(cliente(_usuario())[0], "incorrecta1"),
        "cuenta inactiva": _login(cliente(_usuario(is_active=False))[0]),
        "cuenta bloqueada": _login(cliente(_usuario(locked_until=datetime.now(timezone.utc) + timedelta(minutes=5)))[0]),
    }
    assert {r.status_code for r in casos.values()} == {401}
    assert {r.json()["detail"] for r in casos.values()} == {MENSAJE_INVALIDO}, casos


def test_una_cuenta_inactiva_o_bloqueada_no_suma_intentos(cliente):
    inactiva, bloqueada = _usuario(is_active=False), _usuario(locked_until=datetime.now(timezone.utc) + timedelta(minutes=5))
    _login(cliente(inactiva)[0], "incorrecta1")
    _login(cliente(bloqueada)[0], "incorrecta1")
    assert inactiva.failed_login_attempts == 0 and bloqueada.failed_login_attempts == 0


# ------------------------------------------------------------------ cambio de contraseña (RNF-02)
def _cambiar(c, u, actual=CLAVE, nueva=CLAVE_NUEVA):
    return c.post("/change-password", headers=_auth(u), json={"current_password": actual, "new_password": nueva})


def test_cambiar_la_contrasena_quita_la_marca_y_emite_un_token_nuevo(cliente):
    u = _usuario(must_change_password=True, failed_login_attempts=2)
    c, sesion = cliente(u)
    r = _cambiar(c, u)
    assert r.status_code == 200, r.text
    assert "mcp" not in _claims(r.json()["access_token"])
    assert r.json()["user"]["must_change_password"] is False
    assert verify_password(CLAVE_NUEVA, u.password_hash) and not verify_password(CLAVE, u.password_hash)
    assert u.must_change_password is False and u.password_changed_at is not None and u.failed_login_attempts == 0
    assert sesion.commits == 1


def test_quien_debe_cambiar_la_clave_puede_ver_su_perfil_y_cambiarla_pero_nada_mas(cliente):
    u = _usuario(role="admin", must_change_password=True)
    c, _ = cliente(u)
    assert c.get("/me", headers=_auth(u)).status_code == 200
    assert c.get("/users", headers=_auth(u)).status_code == 403
    assert c.get("/roles", headers=_auth(u)).status_code == 403
    assert _cambiar(c, u).status_code == 200
    # ya cambiada la contraseña, el mismo usuario deja de estar restringido
    assert c.get("/roles", headers=_auth(u)).status_code not in (401, 403)


def test_cambiar_con_la_contrasena_actual_equivocada_se_rechaza_y_cuenta_como_fallo(cliente):
    u = _usuario()
    c, _ = cliente(u)
    r = _cambiar(c, u, actual="incorrecta1")
    assert r.status_code == 401 and "actual no es correcta" in r.json()["detail"]
    assert u.failed_login_attempts == 1 and verify_password(CLAVE, u.password_hash)


def test_un_token_robado_no_puede_adivinar_la_contrasena_actual_sin_limite(cliente):
    u = _usuario()
    c, _ = cliente(u)
    for _ in range(lockout.MAX_FAILED_ATTEMPTS):
        _cambiar(c, u, actual="incorrecta1")
    assert u.locked_until is not None
    r = _cambiar(c, u)  # ni con la actual correcta mientras esté bloqueada
    assert r.status_code == 401 and verify_password(CLAVE, u.password_hash)


def test_la_contrasena_nueva_debe_ser_distinta_y_cumplir_la_complejidad(cliente):
    u = _usuario()
    c, _ = cliente(u)
    assert _cambiar(c, u, nueva=CLAVE).status_code == 422
    for debil in ("corta1", "sololetrasminusculas", "12345678"):
        assert _cambiar(c, u, nueva=debil).status_code == 422, debil
    assert verify_password(CLAVE, u.password_hash), "los rechazos no cambian la contraseña"


def test_cambiar_la_contrasena_exige_sesion(cliente):
    c, _ = cliente(_usuario())
    r = c.post("/change-password", json={"current_password": CLAVE, "new_password": CLAVE_NUEVA})
    assert r.status_code in (401, 403)


# ------------------------------------------------------------------ matriz de roles de auth-service (RF-03)
ADMIN, TODOS = {"admin"}, {"admin", "operador"}
MATRIZ = {
    ("POST", "/login"): None,  # pública
    ("GET", "/me"): TODOS,
    ("POST", "/change-password"): TODOS,
    ("GET", "/roles"): ADMIN,
    ("POST", "/users"): ADMIN,
    ("GET", "/users"): ADMIN,
    ("GET", "/users/{user_id}"): ADMIN,
    ("PATCH", "/users/{user_id}"): ADMIN,
    ("POST", "/users/{user_id}/unlock"): ADMIN,
}
ID = "11111111-1111-1111-1111-111111111111"


def test_la_matriz_cubre_todos_los_endpoints_de_auth_service():
    rutas = {(m, r.path) for r in app.routes if isinstance(r, APIRoute) for m in r.methods - {"HEAD", "OPTIONS"}}
    assert rutas - {("GET", "/health")} == set(MATRIZ)


@pytest.mark.parametrize("metodo,ruta", sorted(k for k, v in MATRIZ.items() if v))
def test_sin_token_se_rechaza(cliente, metodo, ruta):
    c, _ = cliente(_usuario())
    assert c.request(metodo, ruta.replace("{user_id}", ID), json={}).status_code in (401, 403)


@pytest.mark.parametrize("metodo,ruta", sorted(k for k, v in MATRIZ.items() if v))
@pytest.mark.parametrize("rol", ["admin", "operador"])
def test_cada_rol_recibe_lo_que_la_matriz_dice(cliente, metodo, ruta, rol):
    u = _usuario(role=rol)
    c, _ = cliente(u)
    estado = c.request(metodo, ruta.replace("{user_id}", ID), headers=_auth(u), json={}).status_code
    if rol in MATRIZ[(metodo, ruta)]:
        assert estado not in (401, 403), f"{rol} debería poder {metodo} {ruta}, recibió {estado}"
    else:
        assert estado == 403, f"{rol} no debería poder {metodo} {ruta}, recibió {estado}"


@pytest.mark.parametrize("metodo,ruta", sorted(k for k, v in MATRIZ.items() if v == ADMIN))
def test_un_admin_con_cambio_de_clave_pendiente_no_administra_nada(cliente, metodo, ruta):
    u = _usuario(role="admin", must_change_password=True)
    c, _ = cliente(u)
    r = c.request(metodo, ruta.replace("{user_id}", ID), headers=_auth(u), json={})
    assert r.status_code == 403 and "cambiar su contraseña" in r.json()["detail"]
