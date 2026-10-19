"""Capturas en alta resolución y video del recorrido para el README (con la pila local corriendo).

Requiere: `pip install playwright` y Microsoft Edge (o Chrome con --canal chrome). Usa el usuario de prueba del
entorno local de desarrollo (`admin`, ver README) y la base de prueba ficticia.

    docker compose up -d
    python scripts/capturas_readme.py            # escribe docs/capturas/*.png y docs/video/recorrido.webm
"""
import argparse
import json
import shutil
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
WEB, API = 'http://localhost:5173', 'http://localhost:8080/api'
USUARIO, CLAVE = 'admin', 'Admin1234'  # usuario de prueba del entorno local (auth-service/app/seed.py)
CAP, VID = RAIZ / 'docs/capturas', RAIZ / 'docs/video'


def api(metodo, ruta, token=None, datos=None):
    req = urllib.request.Request(API + ruta, method=metodo, data=json.dumps(datos).encode() if datos else None,
                                 headers={'Content-Type': 'application/json',
                                          **({'Authorization': f'Bearer {token}'} if token else {})})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b'null')


def credencial_demo():
    """Emite una credencial QR para un conductor ficticio de la base de prueba y devuelve el enlace de despacho."""
    token = api('POST', '/auth/login', datos={'username': USUARIO, 'password': CLAVE})['access_token']
    conductores = api('GET', '/fleet/drivers', token)
    c = next(d for d in conductores if d['full_name'] == 'Andrés Chávez')
    emitido = api('POST', f"/fleet/drivers/{c['id']}/regenerate-qr", token, {})
    return f"{WEB}/despacho?driverId={c['id']}#token={emitido['qr_token']}"


def entrar(page):
    page.goto(WEB + '/login')
    page.wait_for_selector('input')
    page.locator('input').nth(0).fill(USUARIO)
    page.locator('input').nth(1).fill(CLAVE)
    page.get_by_role('button', name='Ingresar').click()
    page.wait_for_url(WEB + '/')
    page.wait_for_timeout(2500)


def anio(page):
    page.get_by_role('button', name='Año').first.click()
    page.wait_for_timeout(2500)


def capturas(b, enlace):
    CAP.mkdir(parents=True, exist_ok=True)
    ctx = b.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=2, locale='es-EC')
    p = ctx.new_page()
    p.goto(WEB + '/login')
    p.wait_for_timeout(2500)
    p.screenshot(path=CAP / '01_inicio_sesion.png')
    entrar(p)
    anio(p)
    p.screenshot(path=CAP / '02_tablero.png')
    p.get_by_text('Estructura de costos').first.evaluate("e => e.scrollIntoView({block: 'start'})")
    p.wait_for_timeout(1200)
    p.screenshot(path=CAP / '03_estructura_costos.png')
    p.get_by_text('Acción requerida').first.evaluate("e => e.scrollIntoView({block: 'start'})")
    p.wait_for_timeout(1200)
    p.screenshot(path=CAP / '04_alertas_y_prioridad.png')
    for ruta, nombre in (('/mantenimiento', '05_ranking_ahp'), ('/viajes', '06_viajes'), ('/vehiculos', '07_vehiculos'),
                         ('/costos', '08_costos_fijos'), ('/reportes', '09_reportes')):
        p.goto(WEB + ruta)
        p.wait_for_timeout(2500)
        p.screenshot(path=CAP / f'{nombre}.png')
    ctx.close()
    movil = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True,
                          has_touch=True, locale='es-EC')
    m = movil.new_page()
    m.goto(enlace)
    m.wait_for_timeout(3000)
    m.screenshot(path=CAP / '10_despacho_movil.png')
    movil.close()


def video(b, enlace):
    VID.mkdir(parents=True, exist_ok=True)
    ctx = b.new_context(viewport={'width': 1280, 'height': 800}, record_video_dir=str(VID),
                        record_video_size={'width': 1280, 'height': 800}, locale='es-EC')
    p = ctx.new_page()
    p.goto(WEB + '/login')
    p.wait_for_timeout(1500)
    p.locator('input').nth(0).click()
    p.locator('input').nth(0).type(USUARIO, delay=120)
    p.locator('input').nth(1).type(CLAVE, delay=90)
    p.wait_for_timeout(500)
    p.get_by_role('button', name='Ingresar').click()
    p.wait_for_url(WEB + '/')
    p.wait_for_timeout(2500)
    anio(p)
    p.wait_for_timeout(1500)
    for _ in range(14):  # recorre el tablero hacia abajo
        p.mouse.wheel(0, 260)
        p.wait_for_timeout(450)
    p.wait_for_timeout(1500)
    for ruta in ('/mantenimiento', '/viajes', '/vehiculos', '/costos', '/reportes'):
        p.goto(WEB + ruta)
        p.wait_for_timeout(2800)
        p.mouse.wheel(0, 300)
        p.wait_for_timeout(1200)
    p.close()
    nombre = p.video.path()
    ctx.close()
    shutil.move(nombre, VID / 'recorrido_panel.webm')
    movil = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                          record_video_dir=str(VID), record_video_size={'width': 390, 'height': 844}, locale='es-EC')
    m = movil.new_page()
    m.goto(enlace)
    m.wait_for_timeout(3500)
    m.mouse.wheel(0, 400)
    m.wait_for_timeout(2500)
    m.close()
    nombre = m.video.path()
    movil.close()
    shutil.move(nombre, VID / 'recorrido_despacho.webm')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--canal', default='msedge')
    a = ap.parse_args()
    enlace = credencial_demo()
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel=a.canal)
        capturas(b, enlace)
        video(b, enlace)
        b.close()
    print('Listo:', CAP, VID)


if __name__ == '__main__':
    main()
