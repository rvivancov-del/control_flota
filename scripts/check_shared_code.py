"""Comprueba que los archivos que se copian a propósito entre los tres microservicios sigan siendo
idénticos.

Los tres servicios son procesos independientes, cada uno con su propia imagen de Docker: no comparten
un paquete de Python en tiempo de ejecución (extraerlo a una librería común exigiría publicarla o
montarla en cada imagen, más complejidad de despliegue de la que se justifica a este tamaño). Donde
la lógica es literalmente la misma — hoy, solo `app/core/config_guard.py` (RNF-02): el resto de
`core/` (security.py, deps.py, database.py) difiere a propósito entre servicios, según qué necesita
cada uno — se copia adrede, y este script detecta si una copia se editó sin llevar el cambio a las
otras.

Uso (desde la raíz del repositorio; solo biblioteca estándar):
    python scripts/check_shared_code.py

Sale con 0 si todas las copias coinciden byte a byte; con 1 y un diff legible si alguna se separó.
"""
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ("auth-service", "fleet-core-service", "reporting-service")

# Rutas relativas a services/<servicio>/ que deben ser idénticas en los tres.
SHARED_FILES = (
    "app/core/config_guard.py",
)


def main() -> None:
    ok = True
    for relative in SHARED_FILES:
        contents = {}
        for service in SERVICES:
            path = ROOT / "services" / service / relative
            if not path.exists():
                print(f"FALTA: {path}", file=sys.stderr)
                ok = False
                continue
            contents[service] = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        reference_service, reference_text = next(iter(contents.items()))
        for service, text in contents.items():
            if text != reference_text:
                ok = False
                print(f"\n{relative}: {service} difiere de {reference_service}", file=sys.stderr)
                diff = difflib.unified_diff(
                    reference_text.splitlines(keepends=True), text.splitlines(keepends=True),
                    fromfile=f"{reference_service}/{relative}", tofile=f"{service}/{relative}",
                )
                sys.stderr.writelines(diff)
    if not ok:
        sys.exit(
            "\nAlguna copia se separó de las demás: aplique el mismo cambio a las tres, o si el cambio "
            "es legítimo solo para ese servicio, sáquelo de SHARED_FILES en scripts/check_shared_code.py "
            "y documente por qué difiere ahora."
        )
    print(f"Las {len(SHARED_FILES)} copias compartidas coinciden en los {len(SERVICES)} servicios.")


if __name__ == "__main__":
    main()
