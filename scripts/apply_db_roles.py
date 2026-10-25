"""Aplica infra/postgres/roles.sql a una base de datos QUE YA EXISTE.

Una base creada antes de esta separación (o sembrada por seed_demo.py/bench_queries.py con el
superusuario) tiene sus esquemas y tablas en manos de POSTGRES_USER: `docker-entrypoint-initdb.d`
solo corre en un volumen vacío, así que una base ya inicializada nunca ve infra/postgres/init.sh por
su cuenta. Este script hace lo mismo que init.sh, pero de forma explícita y contra la base indicada:
crea (o reutiliza) los roles flota_auth/flota_fleet, crea los esquemas si faltan y transfiere a cada
rol la propiedad de lo que hoy es del superusuario. roles.sql es idempotente: correrlo dos veces no
hace daño.

Uso (desde la raíz del repositorio, con la pila levantada):
    python scripts/apply_db_roles.py --db flota_db --viva                 # base viva del proyecto por defecto
    python scripts/apply_db_roles.py --project flota_verif --db flota_db  # pila de verificación
    python scripts/apply_db_roles.py --db flota_seed --auth-password ... --fleet-password ...

Sin --auth-password/--fleet-password se generan al azar y se muestran una sola vez al final: hay que
copiarlas a POSTGRES_PASSWORD en el .env de auth-service y de fleet-core-service (deben coincidir con
AUTH_DB_PASSWORD/FLEET_DB_PASSWORD del entorno de postgres en docker-compose.yml) y recrear los
contenedores (`docker compose up -d --force-recreate auth-service fleet-core-service`) para que tomen
el rol nuevo. Antes de tocar la base viva, respalde con pg_dump (ver scripts/README.md).
"""
import argparse
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLES_SQL = ROOT / "infra" / "postgres" / "roles.sql"
LIVE_DB = "flota_db"


def compose_base(project: str | None) -> list[str]:
    if project:
        return ["docker", "compose", "-p", project]
    return ["docker", "compose"]


def run(project: str | None, *args: str, stdin: str | None = None) -> str:
    result = subprocess.run(compose_base(project) + list(args), cwd=ROOT, input=stdin, capture_output=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"Falló: docker compose {' '.join(args)}\n{result.stderr.strip()[-2000:]}")
    return result.stdout


def psql_admin(project: str | None, admin_user: str, db: str, sql: str) -> str:
    return run(project, "exec", "-T", "postgres", "psql", "-U", admin_user, "-d", db, "-v", "ON_ERROR_STOP=1", stdin=sql)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="flota_db", help="base de destino (por defecto flota_db)")
    ap.add_argument("--project", help="proyecto de docker compose (omítalo para la pila de trabajo por defecto)")
    ap.add_argument("--admin-user", default="flota", help="superusuario de la instancia (POSTGRES_USER, por defecto 'flota')")
    ap.add_argument("--viva", action="store_true", help="confirma explícitamente que --db flota_db del proyecto por defecto es la base viva")
    ap.add_argument("--auth-password", help="contraseña de flota_auth (si no la da, se genera una)")
    ap.add_argument("--fleet-password", help="contraseña de flota_fleet (si no la da, se genera una)")
    args = ap.parse_args()

    if args.db == LIVE_DB and args.project is None and not args.viva:
        sys.exit("'flota_db' de la pila por defecto es la base viva: agregue --viva si de verdad quiere tocarla (respalde antes con pg_dump).")

    auth_password = args.auth_password or secrets.token_urlsafe(24)
    fleet_password = args.fleet_password or secrets.token_urlsafe(24)
    for nombre, valor in (("--auth-password", auth_password), ("--fleet-password", fleet_password)):
        if "'" in valor or "\n" in valor:
            sys.exit(f"{nombre} no puede llevar comillas simples ni saltos de línea (lo recibe \\set de psql entre comillas).")

    preamble = f"\\set auth_password '{auth_password}'\n\\set fleet_password '{fleet_password}'\n"
    sql = preamble + ROLES_SQL.read_text(encoding="utf-8")
    print(f"Aplicando roles.sql a la base '{args.db}'" + (f" del proyecto '{args.project}'" if args.project else "") + "…")
    salida = psql_admin(args.project, args.admin_user, args.db, sql)
    print(salida.strip() or "(sin salida — psql no mostró NOTICE)")

    print("\nListo. Copie estas contraseñas a POSTGRES_PASSWORD en el .env de cada servicio (deben coincidir con")
    print("AUTH_DB_PASSWORD / FLEET_DB_PASSWORD del entorno de postgres en docker-compose.yml) y recree los contenedores:")
    print(f"  auth-service (POSTGRES_USER=flota_auth):   {auth_password}")
    print(f"  fleet-core-service (POSTGRES_USER=flota_fleet): {fleet_password}")
    print("  docker compose up -d --force-recreate auth-service fleet-core-service   # o con -p <proyecto>")


if __name__ == "__main__":
    main()
