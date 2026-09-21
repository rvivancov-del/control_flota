"""Crea una base de datos de demostración reproducible con la base piloto.

Uso (desde la raíz del repositorio, con `docker compose up` corriendo):
    python scripts/seed_demo.py                 # crea/recrea la base 'flota_seed'
    python scripts/seed_demo.py --db mi_base    # otra base de destino

Pasos: recrea la base de destino, crea el esquema `fleet`, aplica las migraciones
de Alembic de fleet-core-service, carga scripts/seed/pilot_dataset.sql y verifica
conteos y sumas contra el manifiesto. Los conductores quedan sin credencial de
despacho por QR: se genera desde el panel (Conductores -> Generar QR).
NUNCA toca la base viva (`flota_db`): el script se niega a usarla como destino.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "scripts" / "seed"
LIVE_DB = "flota_db"


def compose(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(
        ["docker", "compose", *args], cwd=ROOT, input=stdin, capture_output=True,
        encoding="utf-8", check=False,
    )
    if result.returncode != 0:
        sys.exit(f"Falló: docker compose {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout


def psql(db: str, query: str | None = None, sql: str | None = None) -> str:
    base = ["exec", "-T", "postgres", "psql", "-U", "flota", "-d", db, "-At", "-v", "ON_ERROR_STOP=1"]
    if sql is not None:
        return compose(*base, stdin=sql)
    return compose(*base, "-c", query)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="flota_seed", help="base de destino (por defecto flota_seed)")
    db = ap.parse_args().db
    if db == LIVE_DB or db in ("postgres", "template0", "template1"):
        sys.exit(f"Me niego a usar '{db}' como destino: es la base viva o una base del sistema.")
    if not db.replace("_", "").isalnum():
        sys.exit("Nombre de base inválido (solo letras, números y guion bajo).")

    manifest = json.loads((SEED_DIR / "pilot_dataset.manifest.json").read_text(encoding="utf-8"))
    dataset = (SEED_DIR / "pilot_dataset.sql").read_text(encoding="utf-8")
    if hashlib.sha256(dataset.replace("\r\n", "\n").encode("utf-8")).hexdigest() != manifest["sha256_pilot_dataset_sql"]:
        sys.exit("pilot_dataset.sql no coincide con el hash del manifiesto: ¿se editó a mano? Reexporte con export_pilot_dataset.py.")

    print(f"[1/5] Recreando la base '{db}'…")
    psql("postgres", f"DROP DATABASE IF EXISTS {db} WITH (FORCE)")
    psql("postgres", f"CREATE DATABASE {db}")
    print("[2/5] Creando el esquema fleet…")
    psql(db, "CREATE SCHEMA fleet")
    print("[3/5] Aplicando migraciones de Alembic (fleet-core-service)…")
    compose("exec", "-T", "-e", f"POSTGRES_DB={db}", "fleet-core-service", "alembic", "upgrade", "head")
    print("[4/5] Cargando la base piloto…")
    psql(db, sql=dataset)
    print("[5/5] Verificando contra el manifiesto…")
    ok = True
    for table, expected in manifest["counts"].items():
        got = int(psql(db, f"select count(*) from fleet.{table}").strip())
        flag = "OK" if got == expected else "DIFIERE"
        ok &= got == expected
        print(f"      {table:22s} {got:6d} (esperado {expected}) {flag}")
    checks = {
        "expenses_amount": "select coalesce(sum(amount),0) from fleet.expenses",
        "trips_revenue": "select coalesce(sum(revenue),0) from fleet.trips",
        "maintenance_cost": "select coalesce(sum(cost),0) from fleet.maintenance_records",
        "vehicles_mileage_km": "select coalesce(sum(current_mileage_km),0) from fleet.vehicles",
    }
    for key, query in checks.items():
        got = Decimal(psql(db, query).strip())
        expected = Decimal(manifest["sums"][key])
        flag = "OK" if got == expected else "DIFIERE"
        ok &= got == expected
        print(f"      {key:22s} {got} (esperado {expected}) {flag}")
    if not ok:
        sys.exit("La base cargada no coincide con el manifiesto.")
    print(f"Listo: base '{db}' reproducida y verificada.")


if __name__ == "__main__":
    main()
