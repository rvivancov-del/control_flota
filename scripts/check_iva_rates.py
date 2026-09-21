"""Comprueba que las tarifas de IVA del backend y del frontend coinciden.

Las tarifas viven en dos lugares porque hacen dos trabajos distintos:
  - services/reporting-service/app/dashboards/iva_config.json: las que usa el tablero, los reportes y las
    exportaciones para pasar de monto pagado (bruto) a monto sin IVA (neto).
  - frontend/src/utils/tax.ts: las que usa la pantalla de gastos para descomponer un monto en base + IVA.

Si difieren, una misma compra mostraría dos netos distintos según la pantalla. Este script las compara.

Uso (desde la raíz del repositorio; solo biblioteca estándar):
    python scripts/check_iva_rates.py             # falla si las tarifas difieren
    python scripts/check_iva_rates.py --estricto  # además falla si el contador aún no las verificó

Salida: 0 = coinciden (y, con --estricto, verificadas); 1 = difieren o sin verificar; 2 = no se pudo leer.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "services" / "reporting-service" / "app" / "dashboards" / "iva_config.json"
TAX_TS = ROOT / "frontend" / "src" / "utils" / "tax.ts"
VERIFIED = "verificado_por_contador"


def frontend_rates() -> dict[str, float]:
    text = TAX_TS.read_text(encoding="utf-8")
    block = re.search(r"IVA_RATES\s*:[^=]*=\s*\{(.*?)\}", text, re.S)
    if not block:
        sys.exit(f"No encontré IVA_RATES en {TAX_TS}")
    rates = {key: float(value) for key, value in re.findall(r"(\w+)\s*:\s*([0-9.]+)\s*,", block.group(1))}
    if not rates:
        sys.exit(f"IVA_RATES de {TAX_TS} no tiene tarifas legibles")
    return rates


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estricto", action="store_true", help="falla también si las tarifas no están verificadas por el contador")
    strict = ap.parse_args().estricto

    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        backend = {key: float(value) for key, value in config["tarifas"].items()}
        front = frontend_rates()
    except (OSError, KeyError, ValueError) as exc:
        print(f"No se pudieron leer las tarifas: {exc}", file=sys.stderr)
        sys.exit(2)

    problems = []
    for category, rate in sorted(front.items()):
        if category not in backend:
            problems.append(f"'{category}' está en tax.ts ({rate}) pero no en iva_config.json")
        elif abs(backend[category] - rate) > 1e-9:
            problems.append(f"'{category}': tax.ts {rate} vs iva_config.json {backend[category]}")
    for category in ("combustible", "peaje", "alimentacion", "mantenimiento"):
        if category not in front:
            problems.append(f"'{category}' no está en IVA_RATES de tax.ts")

    for category in sorted(front):
        print(f"  {category:14s} tax.ts {front[category]:.2f}   iva_config.json {backend.get(category, float('nan')):.2f}")
    print(f"Estado de las tarifas: {config['estado']} (versión {config['version']})")
    if problems:
        print("DIFIEREN:\n  - " + "\n  - ".join(problems))
        sys.exit(1)
    print("Las tarifas de tax.ts e iva_config.json coinciden.")
    if config["estado"] != VERIFIED:
        print("AVISO: siguen sin verificar por un contador o por el SRI; las cifras 'sin IVA' son provisionales.")
        if strict:
            sys.exit(1)


if __name__ == "__main__":
    main()
