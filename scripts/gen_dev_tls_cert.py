"""Genera un certificado TLS autofirmado para probar HTTPS en local (RNF-02) con `docker-compose.prod.yml`.

No es de una autoridad de confianza: el navegador mostrará una advertencia la primera vez (es
autofirmado, a propósito, para no depender de una CA externa en un equipo de desarrollo). Si tiene
`mkcert` instalado (https://github.com/FiloSottile/mkcert), úselo en su lugar — genera un certificado
que el navegador acepta sin advertencia porque instala su propia CA local de confianza:

    mkcert -install
    mkcert -cert-file infra/nginx/certs/dev.crt -key-file infra/nginx/certs/dev.key localhost 127.0.0.1

Este script es el respaldo cuando no hay `mkcert` a mano: usa `openssl` (viene con Git para Windows) para
un certificado autofirmado válido 825 días, con `localhost` y `127.0.0.1` como nombres alternativos (los
navegadores actuales exigen el SAN; el CN solo no basta). Los archivos quedan en infra/nginx/certs/, que
está en .gitignore: nunca se versiona una clave privada, ni siquiera la de un certificado de prueba.

Uso (desde la raíz del repositorio):
    python scripts/gen_dev_tls_cert.py            # no hace nada si ya existen
    python scripts/gen_dev_tls_cert.py --forzar    # los regenera
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERT_DIR = ROOT / "infra" / "nginx" / "certs"
CERT = CERT_DIR / "dev.crt"
KEY = CERT_DIR / "dev.key"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forzar", action="store_true", help="regenera el certificado aunque ya exista")
    args = ap.parse_args()

    if CERT.exists() and KEY.exists() and not args.forzar:
        print(f"Ya existen {CERT} y {KEY}. Use --forzar para regenerarlos.")
        return

    if shutil.which("openssl") is None:
        sys.exit("No se encontró 'openssl' en el PATH. En Windows viene con Git para Windows (Git Bash).")

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
        "-days", "825",
        "-keyout", str(KEY), "-out", str(CERT),
        "-subj", "/CN=localhost",
        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Certificado autofirmado escrito en {CERT} y {KEY} (825 días).")
    print("El navegador mostrará una advertencia de certificado no confiable: es esperado (no es de una CA real).")
    print("Para uno sin advertencia, instale mkcert y vuelva a leer la cabecera de este script.")


if __name__ == "__main__":
    main()
