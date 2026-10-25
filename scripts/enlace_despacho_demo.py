"""Enlace del portal de despacho (RF-18) para una demostración en el navegador, con la pila local corriendo.

Emite una credencial QR nueva para un conductor ficticio de la base de prueba (la anterior deja de funcionar,
igual que con «Generar código nuevo» en la pantalla Conductores) y escribe el enlace que codificaría el QR.
Abierto en el navegador con la vista de celular (F12 → Ctrl+Shift+M), muestra el portal del conductor sin
necesidad de escanear el código con un teléfono. Usa el usuario de prueba del entorno local (`admin`).

    python scripts/enlace_despacho_demo.py
    python scripts/enlace_despacho_demo.py --conductor "Andrés Chávez"
"""
import argparse
import json
import urllib.request

WEB, API = "http://localhost:5173", "http://localhost:8080/api"
USUARIO, CLAVE = "admin", "Admin1234"  # usuario de prueba del entorno local (auth-service/app/seed.py)


def api(metodo: str, ruta: str, token: str | None = None, datos: dict | None = None):
    req = urllib.request.Request(API + ruta, method=metodo, data=json.dumps(datos).encode() if datos is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"null")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conductor", default="Andrés Chávez", help="nombre del conductor ficticio (por defecto: Andrés Chávez)")
    args = ap.parse_args()
    token = api("POST", "/auth/login", datos={"username": USUARIO, "password": CLAVE})["access_token"]
    conductor = next((d for d in api("GET", "/fleet/drivers", token) if d["full_name"] == args.conductor), None)
    if conductor is None:
        raise SystemExit(f"No existe el conductor «{args.conductor}» en la base cargada.")
    emitido = api("POST", f"/fleet/drivers/{conductor['id']}/regenerate-qr", token, {})
    print(f"{WEB}/despacho?driverId={conductor['id']}#token={emitido['qr_token']}")


if __name__ == "__main__":
    main()
