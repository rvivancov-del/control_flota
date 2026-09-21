"""Genera infra/nginx/nginx.verif.conf: la misma configuración del gateway con los límites de tasa
relajados, para la pila de verificación (las pruebas de integración hacen muchos inicios de sesión
seguidos y se bloquearían entre sí). La configuración real (infra/nginx/nginx.conf) no se toca.

Uso, desde la raíz del repositorio:  python scripts/make_verif_nginx.py
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "infra" / "nginx" / "nginx.conf"
TARGET = ROOT / "infra" / "nginx" / "nginx.verif.conf"


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    relaxed, count = re.subn(r"rate=\d+r/m", "rate=6000r/m", text)
    if count == 0:
        raise SystemExit("nginx.conf no tiene límites de tasa (rate=Nr/m): ¿cambió el formato?")
    header = "# GENERADO por scripts/make_verif_nginx.py: límites de tasa relajados, solo para la pila de verificación.\n"
    TARGET.write_text(header + relaxed, encoding="utf-8", newline="\n")
    print(f"escrito {TARGET.relative_to(ROOT)} ({count} límites relajados)")


if __name__ == "__main__":
    main()
