"""Carga costos fijos y de personal ILUSTRATIVOS para ver el modelo de costos completo (Fase 3).

Los valores NO son reales. Salen de una regla determinista y declarada (abajo), y todas las filas llevan
notas que empiezan por "EJEMPLO"; la pantalla Costos muestra un aviso mientras existan. El administrador
las reemplaza con los datos reales del contador. La base piloto no trae costos fijos ni de personal, así
que este script vive aparte y no altera el manifiesto de la base piloto.

Uso (desde la raíz del repositorio, con `docker compose up` corriendo):
    python scripts/seed_costos_ejemplo.py                        # base 'flota_seed'
    python scripts/seed_costos_ejemplo.py --db flota_db --viva   # base viva (exige --viva)
    python scripts/seed_costos_ejemplo.py --project flota_verif  # pila de verificación aislada
    python scripts/seed_costos_ejemplo.py --quitar               # borra solo las filas "EJEMPLO"

Es idempotente: cada ejecución borra las filas "EJEMPLO" anteriores y las vuelve a crear con los mismos
identificadores; nunca toca filas cuyas notas no empiecen por "EJEMPLO".

Regla ilustrativa (USD; ninguna cifra es de mercado ni de la empresa):
  - Valor referencial del vehículo por marca; vida útil 10 años y valor residual 20 % ->
    depreciación mensual = valor x 0,8 / 120.
  - Seguro: 3,2 % del valor al año. Impuestos y matrícula: 450 + 0,2 % del valor al año.
  - Capital (crédito o leasing): 0,7 % del valor al mes, solo para modelos 2020 en adelante.
  - Otros: revisión técnica y permisos, 180 al año.
  - Conductores (orden alfabético): sueldo 600 a 700 en escalones de 25; beneficios sociales =
    32 % del sueldo + 39,17 (aporte patronal, 13.º, fondos de reserva y vacaciones aproximados; 14.º).
"""
import argparse
import subprocess
import sys
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = "flota_db"
NOTE = "EJEMPLO"
VALID_FROM = "2025-09-01"  # antes del primer viaje de la base piloto (2025-09-11)
NAMESPACE = uuid.UUID("6f0a1c1e-3b7d-4c55-9a51-2d6b0b7a9e01")

REFERENCE_VALUE = {
    "Kenworth": 118000, "Volvo": 122000, "Mack": 112000, "Mercedes-Benz": 115000,
    "International": 108000, "Freightliner": 110000, "Peterbilt": 120000, "Scania": 125000,
    "Hino": 62000, "Chevrolet": 58000,
}
DEFAULT_VALUE = 95000


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compose_base(project: str | None) -> list[str]:
    if project:
        return ["docker", "compose", "-p", project, "-f", "docker-compose.yml", "-f", "infra/docker-compose.verif.yml"]
    return ["docker", "compose"]


def psql(project: str | None, db: str, query: str | None = None, sql: str | None = None) -> str:
    cmd = compose_base(project) + ["exec", "-T", "postgres", "psql", "-U", "flota", "-d", db, "-At", "-F", "|", "-v", "ON_ERROR_STOP=1"]
    if query is not None:
        cmd += ["-c", query]
    result = subprocess.run(cmd, cwd=ROOT, input=sql, capture_output=True, encoding="utf-8", check=False)
    if result.returncode != 0:
        sys.exit(f"Falló psql en '{db}':\n{result.stderr.strip()}")
    return result.stdout


def q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def fixed_rows(vehicles: list[tuple[str, str, str, int]]) -> list[tuple]:
    """(vehicle_id, categoría, monto, período, nota) por vehículo; la regla está en el docstring del módulo."""
    rows = []
    for vehicle_id, plate, brand, year in vehicles:
        value = Decimal(REFERENCE_VALUE.get(brand, DEFAULT_VALUE))
        rows.append((vehicle_id, "depreciacion", money(value * Decimal("0.8") / 120), "mensual",
                     f"{NOTE}: vida útil 10 años, residual 20 % sobre valor referencial {value:,.0f} ({plate})".replace(",", ".")))
        rows.append((vehicle_id, "seguro", money(value * Decimal("0.032")), "anual",
                     f"{NOTE}: 3,2 % del valor referencial al año ({plate})"))
        rows.append((vehicle_id, "impuestos", money(Decimal(450) + value * Decimal("0.002")), "anual",
                     f"{NOTE}: matrícula e impuestos, 450 + 0,2 % del valor ({plate})"))
        if year >= 2020:
            rows.append((vehicle_id, "capital", money(value * Decimal("0.007")), "mensual",
                         f"{NOTE}: crédito o leasing, 0,7 % del valor al mes, modelo {year} ({plate})"))
        rows.append((vehicle_id, "otros", money(Decimal(180)), "anual",
                     f"{NOTE}: revisión técnica y permisos ({plate})"))
    return rows


def personnel_rows(drivers: list[tuple[str, str]]) -> list[tuple]:
    rows = []
    for index, (driver_id, _name) in enumerate(drivers):
        salary = Decimal(600 + 25 * (index % 5))
        rows.append((driver_id, "sueldo", money(salary), f"{NOTE}: sueldo mensual ilustrativo"))
        rows.append((driver_id, "beneficios_sociales", money(salary * Decimal("0.32") + Decimal("39.17")),
                     f"{NOTE}: aproximación ilustrativa de aporte patronal, 13.º, 14.º, fondos de reserva y vacaciones"))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="flota_seed", help="base de destino (por defecto flota_seed)")
    ap.add_argument("--project", help="proyecto de docker compose (p. ej. flota_verif, la pila de verificación)")
    ap.add_argument("--viva", action="store_true", help="permite escribir en la base viva (flota_db) del proyecto por defecto")
    ap.add_argument("--quitar", action="store_true", help="solo borra las filas de ejemplo")
    args = ap.parse_args()
    db, project = args.db, args.project

    if db in ("postgres", "template0", "template1") or not db.replace("_", "").isalnum():
        sys.exit(f"Base de destino no válida: '{db}'.")
    if db == LIVE_DB and project is None and not args.viva:
        sys.exit("'flota_db' es la base viva: si de verdad quiere cargar ejemplos ahí, agregue --viva.")

    delete_sql = (
        f"DELETE FROM fleet.fixed_costs WHERE notes LIKE '{NOTE}%';\n"
        f"DELETE FROM fleet.personnel_costs WHERE notes LIKE '{NOTE}%';\n"
    )
    if args.quitar:
        psql(project, db, sql="BEGIN;\n" + delete_sql + "COMMIT;\n")
        print(f"Filas '{NOTE}' borradas de '{db}'.")
        return

    vehicles = []
    for line in psql(project, db, "select id, plate, brand, year from fleet.vehicles order by plate").splitlines():
        vehicle_id, plate, brand, year = line.split("|")
        vehicles.append((vehicle_id, plate, brand, int(year)))
    drivers = []
    for line in psql(project, db, "select id, full_name from fleet.drivers where anonymized_at is null order by full_name").splitlines():
        driver_id, name = line.split("|")
        drivers.append((driver_id, name))
    if not vehicles or not drivers:
        sys.exit(f"'{db}' no tiene vehículos o conductores: cargue antes la base piloto (seed_demo.py).")

    statements = ["BEGIN;", delete_sql.strip()]
    monthly_fixed = Decimal(0)
    for vehicle_id, category, amount, period, note in fixed_rows(vehicles):
        row_id = uuid.uuid5(NAMESPACE, f"fixed/{vehicle_id}/{category}")
        statements.append(
            "INSERT INTO fleet.fixed_costs (id, vehicle_id, category, amount, period, valid_from, valid_to, notes) "
            f"VALUES ('{row_id}', '{vehicle_id}', '{category}', {amount}, '{period}', '{VALID_FROM}', NULL, {q(note)});"
        )
        monthly_fixed += amount if period == "mensual" else amount / 12
    monthly_personnel = Decimal(0)
    for driver_id, concept, amount, note in personnel_rows(drivers):
        row_id = uuid.uuid5(NAMESPACE, f"personnel/{driver_id}/{concept}")
        statements.append(
            "INSERT INTO fleet.personnel_costs (id, driver_id, concept, amount, valid_from, valid_to, notes) "
            f"VALUES ('{row_id}', '{driver_id}', '{concept}', {amount}, '{VALID_FROM}', NULL, {q(note)});"
        )
        monthly_personnel += amount
    statements.append("COMMIT;")
    psql(project, db, sql="\n".join(statements) + "\n")

    n_fixed = int(psql(project, db, f"select count(*) from fleet.fixed_costs where notes like '{NOTE}%'").strip())
    n_pers = int(psql(project, db, f"select count(*) from fleet.personnel_costs where notes like '{NOTE}%'").strip())
    print(f"Base '{db}': {n_fixed} costos fijos y {n_pers} de personal de ejemplo "
          f"({len(vehicles)} vehículos, {len(drivers)} conductores).")
    print(f"Equivalente mensual: fijos {money(monthly_fixed)}, personal {money(monthly_personnel)}.")
    print(f"Todas las filas empiezan por '{NOTE}' y se reemplazan desde la pantalla Costos.")


if __name__ == "__main__":
    main()
