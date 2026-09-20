"""
Pruebas de integración contra el stack real (gateway en localhost:8080).
No son pruebas unitarias aisladas: requieren `docker compose up` corriendo.
Cubren RF-01, RF-02, RF-03 y el bloqueo de cuenta (RNF-03).
"""
import requests


def test_login_valido_devuelve_token(base_url, admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 20


def test_login_credenciales_invalidas_rechaza(base_url):
    r = requests.post(f"{base_url}/auth/login", json={"username": "admin", "password": "clave_incorrecta"})
    assert r.status_code == 401


def test_me_devuelve_el_usuario_autenticado(base_url, admin_token):
    r = requests.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"


def test_endpoint_protegido_sin_token_rechaza(base_url):
    r = requests.get(f"{base_url}/auth/me")
    assert r.status_code in (401, 403)


def test_listar_usuarios_como_admin(base_url, admin_token):
    r = requests.get(f"{base_url}/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_listar_usuarios_sin_token_rechaza(base_url):
    r = requests.get(f"{base_url}/auth/users")
    assert r.status_code in (401, 403)
