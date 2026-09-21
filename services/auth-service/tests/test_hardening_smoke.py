"""
Pruebas de integración del bloqueo temporal (RNF-03), el cambio obligatorio de contraseña (RNF-02)
y la protección del último administrador contra el stack real. Crean y desactivan cuentas de
prueba (smoke_*): correrlas contra una base desechable (FLOTA_BASE_URL) con los límites de tasa
del gateway relajados (ver scripts/README.md), porque hacen varios inicios de sesión seguidos.
"""
import requests

CLAVE = "ClavePrueba123"
CLAVE_NUEVA = "ClaveNueva456"
MENSAJE_INVALIDO = "Usuario o contraseña inválidos, o cuenta inactiva o bloqueada temporalmente."


def _login(base_url, usuario, clave):
    return requests.post(f"{base_url}/auth/login", json={"username": usuario, "password": clave})


def _roles(base_url, headers):
    return {r["name"]: r["id"] for r in requests.get(f"{base_url}/auth/roles", headers=headers).json()}


def _cuenta_de_prueba(base_url, headers, username, rol="operador", **extra):
    """Crea la cuenta de prueba o, si ya existe de una corrida anterior, la restablece."""
    role_id = _roles(base_url, headers)[rol]
    usuarios = requests.get(f"{base_url}/auth/users", headers=headers).json()
    existente = next((u for u in usuarios if u["username"] == username), None)
    if existente is None:
        r = requests.post(
            f"{base_url}/auth/users", headers=headers,
            json={"username": username, "password": CLAVE, "full_name": "Cuenta de prueba", "role_id": role_id, **extra},
        )
        assert r.status_code == 201, r.text
        return r.json()
    cambios = {"is_active": True, "password": CLAVE, "role_id": role_id, "must_change_password": extra.get("must_change_password", False)}
    r = requests.patch(f"{base_url}/auth/users/{existente['id']}", headers=headers, json=cambios)
    assert r.status_code == 200, r.text
    requests.post(f"{base_url}/auth/users/{existente['id']}/unlock", headers=headers)
    return r.json()


def _desactivar(base_url, headers, user_id):
    requests.patch(f"{base_url}/auth/users/{user_id}", headers=headers, json={"is_active": False})


# ------------------------------------------------------------------ RNF-03: bloqueo temporal y desbloqueo
def test_cinco_fallos_bloquean_la_cuenta_y_el_admin_puede_desbloquearla(base_url, auth_headers):
    cuenta = _cuenta_de_prueba(base_url, auth_headers, "smoke_bloqueo")
    try:
        assert _login(base_url, "smoke_bloqueo", CLAVE).status_code == 200
        for _ in range(5):
            r = _login(base_url, "smoke_bloqueo", "incorrecta1")
            assert r.status_code == 401 and r.json()["detail"] == MENSAJE_INVALIDO

        # bloqueada (no desactivada): ni la contraseña correcta entra, con el mismo mensaje
        correcto = _login(base_url, "smoke_bloqueo", CLAVE)
        assert correcto.status_code == 401 and correcto.json()["detail"] == MENSAJE_INVALIDO
        vista = requests.get(f"{base_url}/auth/users/{cuenta['id']}", headers=auth_headers).json()
        assert vista["locked_until"] is not None and vista["is_active"] is True

        desbloqueada = requests.post(f"{base_url}/auth/users/{cuenta['id']}/unlock", headers=auth_headers)
        assert desbloqueada.status_code == 200 and desbloqueada.json()["locked_until"] is None
        assert _login(base_url, "smoke_bloqueo", CLAVE).status_code == 200
    finally:
        _desactivar(base_url, auth_headers, cuenta["id"])


def test_reactivar_una_cuenta_tambien_quita_el_bloqueo(base_url, auth_headers):
    cuenta = _cuenta_de_prueba(base_url, auth_headers, "smoke_bloqueo")
    try:
        for _ in range(5):
            _login(base_url, "smoke_bloqueo", "incorrecta1")
        assert _login(base_url, "smoke_bloqueo", CLAVE).status_code == 401
        r = requests.patch(f"{base_url}/auth/users/{cuenta['id']}", headers=auth_headers, json={"is_active": True})
        assert r.status_code == 200 and r.json()["locked_until"] is None
        assert _login(base_url, "smoke_bloqueo", CLAVE).status_code == 200
    finally:
        _desactivar(base_url, auth_headers, cuenta["id"])


def test_solo_el_admin_desbloquea(base_url, auth_headers, operator_headers):
    usuarios = requests.get(f"{base_url}/auth/users", headers=auth_headers).json()
    cualquiera = usuarios[0]["id"]
    assert requests.post(f"{base_url}/auth/users/{cualquiera}/unlock", headers=operator_headers).status_code == 403


# ------------------------------------------------------------------ RNF-02: cambio obligatorio de contraseña
def test_quien_debe_cambiar_la_clave_no_puede_operar_en_ningun_servicio_hasta_cambiarla(base_url, auth_headers):
    cuenta = _cuenta_de_prueba(base_url, auth_headers, "smoke_cambio", must_change_password=True)
    try:
        login = _login(base_url, "smoke_cambio", CLAVE)
        assert login.status_code == 200 and login.json()["user"]["must_change_password"] is True
        pendiente = {"Authorization": f"Bearer {login.json()['access_token']}"}

        assert requests.get(f"{base_url}/auth/me", headers=pendiente).status_code == 200
        for url in ("/auth/users", "/auth/roles", "/fleet/vehicles", "/fleet/drivers", "/reports/dashboard/summary"):
            r = requests.get(f"{base_url}{url}", headers=pendiente)
            assert r.status_code == 403 and "cambiar su contraseña" in r.text, url

        # contraseña actual equivocada, igual a la actual o débil: se rechaza y sigue pendiente
        cambiar = lambda actual, nueva: requests.post(
            f"{base_url}/auth/change-password", headers=pendiente, json={"current_password": actual, "new_password": nueva}
        )
        assert cambiar("incorrecta1", CLAVE_NUEVA).status_code == 401
        assert cambiar(CLAVE, CLAVE).status_code == 422
        assert cambiar(CLAVE, "corta1").status_code == 422
        assert requests.get(f"{base_url}/fleet/vehicles", headers=pendiente).status_code == 403

        ok = cambiar(CLAVE, CLAVE_NUEVA)
        assert ok.status_code == 200 and ok.json()["user"]["must_change_password"] is False
        libre = {"Authorization": f"Bearer {ok.json()['access_token']}"}
        assert requests.get(f"{base_url}/fleet/vehicles", headers=libre).status_code == 200
        assert requests.get(f"{base_url}/reports/dashboard/summary", headers=libre).status_code == 200

        # la contraseña anterior ya no sirve; la nueva sí, y el token viejo sigue restringido hasta que venza
        assert _login(base_url, "smoke_cambio", CLAVE).status_code == 401
        assert _login(base_url, "smoke_cambio", CLAVE_NUEVA).json()["user"]["must_change_password"] is False
        assert requests.get(f"{base_url}/fleet/vehicles", headers=pendiente).status_code == 403
    finally:
        _desactivar(base_url, auth_headers, cuenta["id"])


def test_una_cuenta_normal_no_esta_obligada_a_cambiar_la_clave(base_url, auth_headers):
    cuenta = _cuenta_de_prueba(base_url, auth_headers, "smoke_bloqueo")
    try:
        login = _login(base_url, "smoke_bloqueo", CLAVE)
        assert login.json()["user"]["must_change_password"] is False
        assert requests.get(f"{base_url}/fleet/vehicles", headers={"Authorization": f"Bearer {login.json()['access_token']}"}).status_code == 200
    finally:
        _desactivar(base_url, auth_headers, cuenta["id"])


def test_si_otro_admin_fija_la_contrasena_el_usuario_debe_cambiarla(base_url, auth_headers):
    cuenta = _cuenta_de_prueba(base_url, auth_headers, "smoke_cambio")
    try:
        assert cuenta["must_change_password"] is False
        r = requests.patch(f"{base_url}/auth/users/{cuenta['id']}", headers=auth_headers, json={"password": "OtraClave789"})
        assert r.status_code == 200 and r.json()["must_change_password"] is True
        # salvo que el admin indique lo contrario
        r = requests.patch(
            f"{base_url}/auth/users/{cuenta['id']}", headers=auth_headers,
            json={"password": "OtraClave790", "must_change_password": False},
        )
        assert r.json()["must_change_password"] is False
    finally:
        _desactivar(base_url, auth_headers, cuenta["id"])


# ------------------------------------------------------------------ RNF-03: nunca sin administrador
def test_no_se_puede_dejar_al_sistema_sin_administrador_activo(base_url, auth_headers):
    roles = _roles(base_url, auth_headers)
    admins = [u for u in requests.get(f"{base_url}/auth/users", headers=auth_headers).json() if u["role"]["name"] == "admin" and u["is_active"]]
    unico = next(u for u in admins if u["username"] == "admin")
    extra = [u for u in admins if u["username"] != "admin"]
    if extra:  # deja solo a 'admin' para probar el caso del último administrador
        for u in extra:
            _desactivar(base_url, auth_headers, u["id"])

    for cambios in ({"is_active": False}, {"role_id": roles["operador"]}):
        r = requests.patch(f"{base_url}/auth/users/{unico['id']}", headers=auth_headers, json=cambios)
        assert r.status_code == 409 and "al menos un administrador activo" in r.text, cambios
    vigente = requests.get(f"{base_url}/auth/users/{unico['id']}", headers=auth_headers).json()
    assert vigente["is_active"] is True and vigente["role"]["name"] == "admin"

    # con un segundo administrador activo, el cambio sobre el primero sí se permite (y se revierte)
    segundo = _cuenta_de_prueba(base_url, auth_headers, "smoke_admin2", rol="admin")
    try:
        r = requests.patch(f"{base_url}/auth/users/{segundo['id']}", headers=auth_headers, json={"role_id": roles["operador"]})
        assert r.status_code == 200 and r.json()["role"]["name"] == "operador"
        # 'admin' vuelve a ser el único: sigue protegido
        assert requests.patch(f"{base_url}/auth/users/{unico['id']}", headers=auth_headers, json={"is_active": False}).status_code == 409
    finally:
        _desactivar(base_url, auth_headers, segundo["id"])
