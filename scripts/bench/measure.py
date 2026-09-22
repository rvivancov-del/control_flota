"""Mide las consultas de la API de fleet-core-service contra la base a la que apunta POSTGRES_DB.

Lo ejecuta scripts/bench_queries.py DENTRO del contenedor de fleet-core-service (necesita el código de la
aplicación y sus dependencias); no se corre a mano. Cada consulta se pide a la API real (TestClient: con su
enrutamiento, permisos y serialización, sin red) con un token de administrador fabricado, y se mide:

  - el tiempo de respuesta (mediana y máximo de --reps repeticiones, después de una de calentamiento);
  - el plan de PostgreSQL de cada sentencia SQL que la consulta ejecuta (EXPLAIN ANALYZE): tiempo de
    ejecución, tablas recorridas completas (Seq Scan) e índices usados;
  - qué índices se usaron durante toda la medición (pg_stat_user_indexes).

Además compara el filtro de fechas anterior (`date(departure_at) BETWEEN`) con el actual (intervalo sobre
`departure_at`) sobre la misma consulta, comprobando que devuelven lo mismo. Escribe una línea
`BENCH_JSON: {...}` con todo el resultado.
"""
import argparse
import json
import os
import statistics
import time
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("APP_ENV", "development")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.core import database, security  # noqa: E402
from app.main import app  # noqa: E402

MES = {"date_from": "2026-08-01", "date_to": "2026-08-31"}
ANIO = {"date_from": "2025-09-01", "date_to": "2026-08-31"}


def token() -> dict:
    payload = {"sub": str(uuid.uuid4()), "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return {"Authorization": "Bearer " + jwt.encode(payload, security.JWT_SECRET_KEY, algorithm=security.JWT_ALGORITHM)}


def scalar(sql: str):
    conn = database.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchone()[0]
    finally:
        conn.close()


def walk(node: dict, found: list) -> None:
    """Recoge (tipo de nodo, tabla, índice) de todos los nodos de un plan."""
    found.append((node.get("Node Type"), node.get("Relation Name"), node.get("Index Name")))
    for child in node.get("Plans", []):
        walk(child, found)


def explain(statements: list) -> dict:
    """EXPLAIN ANALYZE de cada sentencia capturada; resume tiempo, recorridos completos e índices."""
    total_ms, seq_scans, indexes = 0.0, set(), set()
    conn = database.engine.raw_connection()
    try:
        cur = conn.cursor()
        for statement, parameters in statements:
            cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + statement, parameters)
            plan = cur.fetchone()[0]
            plan = plan[0] if isinstance(plan, list) else plan
            total_ms += plan["Execution Time"]
            nodes: list = []
            walk(plan["Plan"], nodes)
            for kind, relation, index in nodes:
                if kind == "Seq Scan" and relation in ("trips", "expenses", "maintenance_records"):
                    seq_scans.add(relation)
                if index:
                    indexes.add(index)
    finally:
        conn.rollback()
        conn.close()
    return {"execution_ms": round(total_ms, 2), "seq_scans": sorted(seq_scans), "indexes": sorted(indexes)}


def capturar(client, headers, path, params):
    """Ejecuta una consulta de la API una vez y devuelve las sentencias SELECT que lanzó a la base."""
    captured: list = []

    def antes(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and any(t in statement for t in ("trips", "expenses", "maintenance_records")):
            captured.append((statement, parameters))

    event.listen(database.engine, "before_cursor_execute", antes)
    try:
        client.get(path, headers=headers, params=params)
    finally:
        event.remove(database.engine, "before_cursor_execute", antes)
    return captured


def comparar_predicado(vista: dict) -> dict:
    """Mismo agrupamiento de viajes con el filtro anterior (función sobre la columna) y el actual (intervalo)."""
    base = ("SELECT vehicle_id, driver_id, date(departure_at) AS d, count(id) AS c, sum(end_mileage_km - start_mileage_km) AS s, "
            "coalesce(sum(revenue), 0) AS r FROM trips WHERE status = 'completado' AND {cond} "
            "GROUP BY vehicle_id, driver_id, date(departure_at)")
    anterior = base.format(cond="date(departure_at) >= %(a)s AND date(departure_at) <= %(b)s")
    actual = base.format(cond="departure_at >= %(a)s::timestamptz AND departure_at < %(b2)s::timestamptz")
    a, b = vista["date_from"], vista["date_to"]
    b2 = (datetime.fromisoformat(b) + timedelta(days=1)).date().isoformat()
    params_old, params_new = {"a": a, "b": b}, {"a": a, "b2": b2}
    resumen = "SELECT count(*), coalesce(sum(c), 0), coalesce(sum(s), 0), coalesce(sum(r), 0) FROM ({}) x"
    conn = database.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(resumen.format(anterior), params_old)
        filas_old = cur.fetchone()
        cur.execute(resumen.format(actual), params_new)
        filas_new = cur.fetchone()
    finally:
        conn.close()
    return {
        "mismas_filas": filas_old == filas_new,
        "grupos": int(filas_old[0]),
        "anterior": explain([(anterior, params_old)]),
        "actual": explain([(actual, params_new)]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    args = ap.parse_args()

    client = TestClient(app)
    headers = token()
    vehiculo = scalar("SELECT id FROM vehicles ORDER BY plate LIMIT 1")
    viaje = scalar("SELECT trip_id FROM expenses LIMIT 1")

    consultas = [
        ("gastos agregados (mes)", "/analytics/expenses", MES),
        ("gastos agregados (año)", "/analytics/expenses", ANIO),
        ("viajes agregados (mes)", "/analytics/trips", MES),
        ("viajes agregados (año)", "/analytics/trips", ANIO),
        ("rutas (mes)", "/analytics/routes", MES),
        ("rutas (año)", "/analytics/routes", ANIO),
        ("mantenimiento agregado (año)", "/analytics/maintenance", ANIO),
        ("viajes de un vehículo (mes)", "/trips", {"vehicle_id": str(vehiculo), **MES}),
        ("gastos de un vehículo (mes)", "/expenses", {"vehicle_id": str(vehiculo), **MES}),
        ("gastos de un viaje", f"/trips/{viaje}/expenses", {}),
        ("mantenimientos pendientes de la flota", "/maintenance", {"status_filter": "pendiente"}),
        ("mantenimientos de un vehículo", f"/vehicles/{vehiculo}/maintenance", {}),
    ]

    conn = database.engine.raw_connection()
    try:
        conn.cursor().execute("SELECT pg_stat_reset()")  # solo un superusuario puede; sin permiso, el uso de índices incluye lo anterior
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

    resultados = {}
    for nombre, path, params in consultas:
        respuesta = client.get(path, headers=headers, params=params)  # calentamiento
        assert respuesta.status_code == 200, (nombre, respuesta.status_code, respuesta.text[:200])
        tiempos = []
        for _ in range(args.reps):
            t0 = time.perf_counter()
            client.get(path, headers=headers, params=params)
            tiempos.append((time.perf_counter() - t0) * 1000)
        resultados[nombre] = {
            "mediana_ms": round(statistics.median(tiempos), 1),
            "maximo_ms": round(max(tiempos), 1),
            "filas": len(respuesta.json()),
            "plan": explain(capturar(client, headers, path, params)),
        }

    # PostgreSQL agrega las estadísticas de uso de índices por conexión y las vuelca con retraso: se cierran
    # las del pool y se espera un momento para que la lectura siguiente las vea completas.
    database.engine.dispose()
    time.sleep(2)
    uso = {}
    conn = database.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT indexrelname, idx_scan, pg_relation_size(indexrelid) FROM pg_stat_user_indexes WHERE schemaname = 'fleet' ORDER BY 1")
        for nombre, escaneos, tam in cur.fetchall():
            uso[nombre] = {"usos": escaneos, "bytes": tam}
        cur.execute("SELECT relname, n_live_tup, pg_total_relation_size(relid) FROM pg_stat_user_tables WHERE schemaname = 'fleet' ORDER BY 1")
        tablas = {n: {"filas": f, "bytes": b} for n, f, b in cur.fetchall()}
    finally:
        conn.close()

    salida = {
        "tablas": {t: tablas[t] for t in ("trips", "expenses", "maintenance_records", "vehicles", "drivers") if t in tablas},
        "consultas": resultados,
        "indices": uso,
        "predicado_de_fechas": comparar_predicado(ANIO),
    }
    print("BENCH_JSON: " + json.dumps(salida, ensure_ascii=False))


if __name__ == "__main__":
    main()
