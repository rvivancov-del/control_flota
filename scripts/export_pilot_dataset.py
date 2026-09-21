"""Exporta la base piloto de fleet-core (solo lectura) a un SQL versionable.

Las cifras del documento de tesis (12 vehículos, 13 conductores, 640 viajes,
1.330 gastos, 96 mantenimientos) salen de esta base. El respaldo .sql que había
en el repositorio estaba desactualizado (12/12/622/1.321); este script fija la
base real como conjunto de datos de referencia reproducible.

Uso (desde la raíz del repositorio, con `docker compose up` corriendo):
    python scripts/export_pilot_dataset.py

Genera scripts/seed/pilot_dataset.sql y scripts/seed/pilot_dataset.manifest.json.
Los datos son ficticios; las columnas de credencial de los conductores (token del
QR o su hash, emisión, vigencia, último uso) NO se exportan: la base cargada deja a
cada conductor sin credencial y se genera desde el panel de administración.
"""
import hashlib
import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "scripts" / "seed"
SOURCE_DB = "flota_db"
# Orden de inserción: respeta las claves foráneas.
TABLES = ["vehicles", "drivers", "trips", "expenses", "maintenance_records"]
# Columnas que no se exportan (RF-18: credenciales de despacho). Incluye la columna en claro
# anterior a la migración c3a7e15b9d20 para que el script funcione con cualquiera de los dos esquemas.
EXCLUDE_COLUMNS = {
    "drivers": {"qr_token", "qr_token_hash", "qr_token_issued_at", "qr_token_expires_at", "qr_token_last_used_at"}
}


def psql(query: str) -> list[str]:
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "flota", "-d", SOURCE_DB,
         "-At", "-v", "ON_ERROR_STOP=1", "-c", query],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, Decimal)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def main() -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "-- Base piloto de FlotaControl (datos ficticios). Generado por scripts/export_pilot_dataset.py",
        f"-- Fecha de exportación: {date.today().isoformat()}",
        "SET client_encoding = 'UTF8';",
        "SET search_path = fleet;",
        "BEGIN;",
    ]
    counts = {}
    for table in TABLES:
        rows = [json.loads(r, parse_float=Decimal) for r in psql(
            f"select row_to_json(t) from fleet.{table} t order by t.id")]
        counts[table] = len(rows)
        for row in rows:
            cols = [c for c in row.keys() if c not in EXCLUDE_COLUMNS.get(table, ())]
            vals = [literal(row[c]) for c in cols]
            lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)});")
    lines.append("COMMIT;")
    sql = "\n".join(lines) + "\n"

    sums = {
        "expenses_amount": psql("select coalesce(sum(amount),0) from fleet.expenses")[0],
        "trips_revenue": psql("select coalesce(sum(revenue),0) from fleet.trips")[0],
        "maintenance_cost": psql("select coalesce(sum(cost),0) from fleet.maintenance_records")[0],
        "vehicles_mileage_km": psql("select coalesce(sum(current_mileage_km),0) from fleet.vehicles")[0],
    }
    sql_path = SEED_DIR / "pilot_dataset.sql"
    sql_path.write_text(sql, encoding="utf-8", newline="\n")
    manifest = {
        "exported_on": date.today().isoformat(),
        "source_db": SOURCE_DB,
        "counts": counts,
        "sums": sums,
        "sha256_pilot_dataset_sql": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
    }
    (SEED_DIR / "pilot_dataset.manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("conteos:", counts)
    print("sumas:", sums)
    print("escrito:", sql_path, f"({len(sql.splitlines())} líneas)")


if __name__ == "__main__":
    sys.exit(main())
