"""Benchmark de las consultas de fleet-core-service a 10^3, 10^5 y 10^6 viajes, sin y con los índices de la migración
f4a8c2d6e9b1 (Fase 5). Genera 12_RESULTADOS_OBTENIDOS/benchmark_consultas.md.

Por cada escala: crea una base desechable `flota_bench` dentro de la pila indicada, aplica las migraciones hasta la
anterior a los índices, carga datos sintéticos con generate_series, mide las consultas (scripts/bench/measure.py,
que corre dentro del contenedor de fleet-core-service), aplica la migración de índices, y mide otra vez.

Uso (desde la raíz del repositorio; solo biblioteca estándar; la pila debe estar levantada):
    python scripts/bench_queries.py --project flota_verif                     # 10^3, 10^5 y 10^6 viajes
    python scripts/bench_queries.py --project flota_verif --scales 1000 100000
    python scripts/bench_queries.py --informe                                 # solo regenera el informe desde los JSON

NUNCA toca la base viva ni la de la pila: usa `flota_bench` y la borra al terminar.
Escala = número de viajes; los vehículos y conductores crecen con ella (1 vehículo por cada 1 000 viajes, mínimo 12),
los gastos son ~1,75 por viaje completado y hay un mantenimiento cada 50 viajes.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT.parent / "12_RESULTADOS_OBTENIDOS" / "benchmark"
INFORME = ROOT.parent / "12_RESULTADOS_OBTENIDOS" / "benchmark_consultas.md"
DB = "flota_bench"
BEFORE_REV = "e7c3b9d1a5f4"  # última migración anterior a los índices


def compose_base(project: str | None) -> list[str]:
    if project:
        return ["docker", "compose", "-p", project, "-f", "docker-compose.yml", "-f", "infra/docker-compose.verif.yml"]
    return ["docker", "compose"]


def run(project, *args, stdin=None, check=True):
    result = subprocess.run(compose_base(project) + list(args), cwd=ROOT, input=stdin, capture_output=True, encoding="utf-8")
    if check and result.returncode != 0:
        sys.exit(f"Falló: docker compose {' '.join(args)}\n{result.stderr.strip()[-1500:]}")
    return result.stdout


def psql(project, db, sql=None, query=None):
    base = ["exec", "-T", "postgres", "psql", "-U", "flota", "-d", db, "-At", "-v", "ON_ERROR_STOP=1"]
    return run(project, *base, "-c", query) if query is not None else run(project, *base, stdin=sql)


def alembic(project, target):
    run(project, "exec", "-T", "-e", f"POSTGRES_DB={DB}", "fleet-core-service", "alembic", "upgrade", target)


def datos_sql(n: int) -> str:
    nv = max(12, n // 1000)
    nd = nv + 1
    return f"""
SET search_path = fleet;
INSERT INTO vehicles (id, plate, brand, model, year, current_mileage_km, status)
  SELECT gen_random_uuid(), 'B' || lpad(g::text, 6, '0'), 'Bench', 'X', 2020, 100000, 'activo' FROM generate_series(1, {nv}) g;
INSERT INTO drivers (id, full_name, license_number, license_type, status)
  SELECT gen_random_uuid(), 'Conductor ' || g, 'L' || lpad(g::text, 8, '0'), 'E', 'activo' FROM generate_series(1, {nd}) g;
CREATE TEMP TABLE veh AS SELECT id, row_number() OVER (ORDER BY plate) AS rn FROM vehicles;
CREATE TEMP TABLE drv AS SELECT id, row_number() OVER (ORDER BY license_number) AS rn FROM drivers;
INSERT INTO trips (id, vehicle_id, driver_id, origin, destination, departure_at, arrival_at, start_mileage_km, end_mileage_km, revenue, status)
  SELECT gen_random_uuid(), v.id, d.id, t.o, t.d2, t.ts, t.ts + interval '8 hours', t.s, t.s + t.km,
         round((t.km * (1.2 + random() * 0.6))::numeric, 2),
         CASE WHEN t.p < 0.93 THEN 'completado' WHEN t.p < 0.97 THEN 'anulado' ELSE 'planificado' END
  FROM (SELECT g,
               1 + (g % {nv}) AS vrn, 1 + ((g * 7) % {nd}) AS drn,
               (ARRAY['Guayaquil','Quito','Cuenca','Manta','Loja','Machala'])[1 + (g % 6)] AS o,
               (ARRAY['Quito','Cuenca','Manta','Loja','Machala','Guayaquil'])[1 + ((g / 6) % 6)] AS d2,
               timestamptz '2024-01-01 00:00:00+00' + (random() * 1000) * interval '1 day' AS ts,
               (100000 + (g % 500000))::int AS s, (50 + random() * 450)::int AS km, random() AS p
        FROM generate_series(1, {n}) g) t
  JOIN veh v ON v.rn = t.vrn JOIN drv d ON d.rn = t.drn;
INSERT INTO expenses (id, trip_id, type, amount, liters, currency, expense_date, location)
  SELECT gen_random_uuid(), t.id, x.kind, round((x.base * (0.5 + random()))::numeric, 2),
         CASE WHEN x.kind = 'combustible' THEN round((60 + random() * 140)::numeric, 2) END, 'USD',
         (t.departure_at AT TIME ZONE 'UTC')::date, CASE WHEN x.kind = 'peaje' THEN 'Peaje de prueba' END
  FROM trips t CROSS JOIN (VALUES ('combustible', 120.0), ('peaje', 8.0), ('alimentacion', 12.0)) AS x(kind, base)
  WHERE t.status = 'completado' AND (x.kind = 'combustible' OR random() < 0.5);
INSERT INTO maintenance_records (id, vehicle_id, maintenance_type, category, scheduled_mileage_km, performed_mileage_km, cost, performed_at, status)
  SELECT gen_random_uuid(), v.id, (ARRAY['aceite','filtros','llantas','frenos','otro'])[1 + (g % 5)],
         (ARRAY['preventivo','correctivo','programado_km'])[1 + (g % 3)],
         CASE WHEN g % 5 = 0 THEN 100000 + g END, CASE WHEN g % 5 <> 0 THEN 100000 + g END,
         CASE WHEN g % 5 <> 0 THEN round((50 + random() * 400)::numeric, 2) END,
         CASE WHEN g % 5 <> 0 THEN date '2024-01-01' + (random() * 1000)::int END,
         CASE WHEN g % 5 = 0 THEN 'pendiente' ELSE 'completado' END
  FROM generate_series(1, {max(n // 50, 10)}) g JOIN veh v ON v.rn = 1 + (g % {nv});
"""


def medir(project, etiqueta, reps):
    salida = run(project, "exec", "-T", "-e", f"POSTGRES_DB={DB}", "-e", "APP_ENV=development", "-e", "PYTHONPATH=/app", "fleet-core-service",
                 "python", "/tmp/measure.py", "--reps", str(reps))
    linea = next((l for l in salida.splitlines() if l.startswith("BENCH_JSON: ")), None)
    if linea is None:
        sys.exit(f"measure.py no devolvió resultados ({etiqueta}):\n{salida[-1500:]}")
    return json.loads(linea[len("BENCH_JSON: "):])


def correr_escala(project, n, reps):
    print(f"\n=== {n:,} viajes ===")
    t0 = time.time()
    psql(project, "postgres", query=f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
    psql(project, "postgres", query=f"CREATE DATABASE {DB}")
    # Dueño flota_fleet (infra/postgres/roles.sql): el rol con el que fleet-core-service se conecta.
    psql(project, DB, query="CREATE SCHEMA fleet AUTHORIZATION flota_fleet")
    alembic(project, BEFORE_REV)
    print(f"  cargando datos sintéticos… ({time.time() - t0:.0f} s)")
    psql(project, DB, sql=datos_sql(n))
    psql(project, DB, query="VACUUM ANALYZE")
    print(f"  midiendo sin índices… ({time.time() - t0:.0f} s)")
    sin = medir(project, "sin índices", reps)
    print(f"  creando índices… ({time.time() - t0:.0f} s)")
    t_idx = time.time()
    alembic(project, "head")
    creacion_s = round(time.time() - t_idx, 1)
    psql(project, DB, query="VACUUM ANALYZE")
    print(f"  midiendo con índices… ({time.time() - t0:.0f} s)")
    con = medir(project, "con índices", reps)
    resultado = {"viajes": n, "sin_indices": sin, "con_indices": con, "creacion_de_indices_s": creacion_s}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"escala_{n}.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  listo en {time.time() - t0:.0f} s")


# ---------------------------------------------------------------------------- informe
def ms(v: float) -> str:
    return f"{v / 1000:.2f} s" if v >= 1000 else f"{v:.1f} ms"


def mb(b: float) -> str:
    return f"{b / 1e6:.0f} MB" if b >= 1e6 else f"{b / 1e3:.0f} kB"


def generar_informe() -> None:
    escalas = sorted(OUT_DIR.glob("escala_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    if not escalas:
        sys.exit(f"No hay resultados en {OUT_DIR}: corra primero el benchmark.")
    datos = [json.loads(p.read_text(encoding="utf-8")) for p in escalas]
    w = []
    w.append("# Benchmark de consultas a 10³, 10⁵ y 10⁶ viajes")
    w.append("")
    w.append("*Generado por `scripts/bench_queries.py` desde `benchmark/escala_*.json`. No se edita a mano: se regenera.*")
    w.append("")
    w.append("## 1. Qué se midió")
    w.append("")
    w.append("Las consultas de fleet-core-service que alimentan el tablero (agregados de gastos, viajes, rutas y mantenimiento por "
             "período) y las listas filtradas de RF-14, pedidas a la API real (con su enrutamiento, permisos y serialización) sobre "
             "una base con datos sintéticos, **sin** y **con** los índices de la migración `f4a8c2d6e9b1`. Cada consulta se repite "
             "5 veces tras una de calentamiento; se informa la mediana. Un *recorrido completo* (Seq Scan) es leer la tabla entera; "
             "es lo que un índice adecuado evita.")
    w.append("")
    w.append("Escalas (número de viajes): " + ", ".join(f"{d['viajes']:,}".replace(",", " ") for d in datos) + ". Los vehículos y "
             "conductores crecen con la escala (1 vehículo por cada 1 000 viajes, mínimo 12); hay ~1,75 gastos por viaje "
             "completado y un mantenimiento cada 50 viajes; los viajes se reparten en unos 1 000 días y las consultas piden un mes "
             "o un año de los últimos.")
    w.append("")
    w.append("| Escala | Viajes | Gastos | Mantenimientos | Tamaño de las tablas | Tamaño de los índices | Crear los índices |")
    w.append("|---|---:|---:|---:|---:|---:|---:|")
    for d in datos:
        t = d["con_indices"]["tablas"]
        tam_tablas = sum(t[x]["bytes"] for x in ("trips", "expenses", "maintenance_records") if x in t)
        tam_indices = sum(v["bytes"] for k, v in d["con_indices"]["indices"].items() if k.startswith("ix_") and not k.startswith("ix_fixed") and not k.startswith("ix_personnel"))
        w.append(f"| {d['viajes']:,} | {t['trips']['filas']:,} | {t['expenses']['filas']:,} | {t['maintenance_records']['filas']:,} | "
                 f"{mb(tam_tablas)} | {mb(tam_indices)} | {d['creacion_de_indices_s']:.1f} s |".replace(",", " "))
    w.append("")
    w.append("## 2. Tiempo de respuesta de la API (mediana)")
    w.append("")
    nombres = list(datos[0]["sin_indices"]["consultas"].keys())
    cab = ["Consulta"]
    for d in datos:
        n = f"{d['viajes']:,}".replace(",", " ")
        cab += [f"{n}: sin", f"{n}: con", "mejora"]
    w.append("| " + " | ".join(cab) + " |")
    w.append("|" + "|".join(["---"] + ["---:"] * (3 * len(datos))) + "|")
    for nombre in nombres:
        fila = [nombre]
        for d in datos:
            a = d["sin_indices"]["consultas"][nombre]["mediana_ms"]
            b = d["con_indices"]["consultas"][nombre]["mediana_ms"]
            fila += [ms(a), ms(b), f"{a / b:.1f}×" if b > 0 else "—"]
        w.append("| " + " | ".join(fila) + " |")
    w.append("")
    w.append("## 3. Plan de ejecución en la base más grande")
    w.append("")
    grande = datos[-1]
    w.append(f"Con {grande['viajes']:,} viajes".replace(",", " ") + ": tablas recorridas por completo (Seq Scan) e índices usados, por consulta.")
    w.append("")
    w.append("| Consulta | Sin índices: recorre completa | Con índices: recorre completa | Con índices: usa |")
    w.append("|---|---|---|---|")
    for nombre in nombres:
        a = grande["sin_indices"]["consultas"][nombre]["plan"]
        b = grande["con_indices"]["consultas"][nombre]["plan"]
        w.append(f"| {nombre} | {', '.join(a['seq_scans']) or '—'} | {', '.join(b['seq_scans']) or '—'} | {', '.join(b['indexes']) or '—'} |")
    w.append("")
    w.append("Las consultas \"(año)\" siguen recorriendo la tabla completa incluso con el índice creado, y su tiempo casi "
             "no cambia (sección 2): con datos repartidos en ~1 000 días, un año cubre más de un tercio de las filas, y el "
             "planificador de PostgreSQL decide — correctamente — que un recorrido secuencial es más barato que ir "
             "índice por índice a buscar un tercio de la tabla. No es una falla del índice: es la selectividad de la "
             "consulta. Las que sí aceleran de forma clara son las de baja selectividad: un mes (una treintava parte del "
             "rango) o un solo vehículo o viaje (sección 2, hasta 10× más rápidas).")
    w.append("")
    w.append("## 4. Filtro de fechas: función sobre la columna frente a intervalo")
    w.append("")
    w.append("La consulta de viajes agregados por vehículo, conductor y día en el último año, con el filtro anterior "
             "(`date(departure_at) BETWEEN …`) y con el actual (`departure_at >= … AND departure_at < …`), con los índices creados. "
             "Devuelven lo mismo en todas las escalas: " + ("sí." if all(d["con_indices"]["predicado_de_fechas"]["mismas_filas"] for d in datos) else "**NO** (revisar).")
             )
    w.append("")
    w.append("| Escala | Filtro anterior | Filtro actual | Mejora |")
    w.append("|---|---:|---:|---:|")
    for d in datos:
        p = d["con_indices"]["predicado_de_fechas"]
        a, b = p["anterior"]["execution_ms"], p["actual"]["execution_ms"]
        w.append(f"| {d['viajes']:,} | {ms(a)} | {ms(b)} | {a / b:.1f}× |".replace(",", " "))
    w.append("")
    w.append("## 5. Índices y su uso")
    w.append("")
    w.append("Veces que la base usó cada índice durante la medición en la escala más grande (0 = no se usó).")
    w.append("")
    w.append("| Índice | Usos | Tamaño |")
    w.append("|---|---:|---:|")
    for nombre, v in grande["con_indices"]["indices"].items():
        if nombre.startswith("ix_trips") or nombre.startswith("ix_expenses") or nombre.startswith("ix_maintenance"):
            w.append(f"| `{nombre}` | {v['usos']} | {mb(v['bytes'])} |")
    w.append("")
    w.append("## 6. Condiciones y límites")
    w.append("")
    w.append("- Datos sintéticos generados con `generate_series` y `random()`; su distribución (uniforme en fechas y vehículos) es más "
             "benigna que la de una flota real. Sirven para comparar con y sin índices y para ver cómo crece el costo, no para predecir "
             "tiempos de producción.")
    w.append("- PostgreSQL 16 en un contenedor de Docker Desktop (Windows 11, 24 CPU, 16 GB) y la API medida dentro del contenedor de "
             "fleet-core-service; no hay red entre ambos en la medición. La base tiene la configuración por defecto de la imagen.")
    w.append("- `GET /trips` y `GET /expenses` sin filtros devuelven todas las filas: con 10⁶ viajes son respuestas de decenas de megabytes. "
             "Los filtros por período o vehículo acotan el resultado; la paginación queda como trabajo pendiente.")
    w.append("- El servicio no cambia con la escala (mismo código y mismos filtros): las diferencias entre columnas son de la base de datos.")
    w.append("")
    INFORME.write_text("\n".join(w) + "\n", encoding="utf-8", newline="\n")
    print(f"Escrito {INFORME}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="proyecto de docker compose de la pila levantada (p. ej. flota_verif)")
    ap.add_argument("--scales", type=int, nargs="+", default=[1000, 100000, 1000000], help="números de viajes")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--informe", action="store_true", help="solo regenera el informe desde los JSON guardados")
    args = ap.parse_args()
    if args.informe:
        generar_informe()
        return
    if args.project is None:
        sys.exit("Indique --project: el benchmark no debe correr contra la pila de trabajo (p. ej. --project flota_verif).")
    run(args.project, "cp", str(ROOT / "scripts" / "bench" / "measure.py"), "fleet-core-service:/tmp/measure.py")
    # El TestClient de FastAPI necesita httpx, que la imagen de producción no trae (solo las pruebas lo usan).
    run(args.project, "exec", "-T", "fleet-core-service", "pip", "install", "-q", "--disable-pip-version-check", "httpx==0.27.2")
    try:
        for n in args.scales:
            correr_escala(args.project, n, args.reps)
    finally:
        psql(args.project, "postgres", query=f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
    generar_informe()


if __name__ == "__main__":
    main()
