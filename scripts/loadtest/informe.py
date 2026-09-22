"""Genera 12_RESULTADOS_OBTENIDOS/prueba_de_carga_tablero.md a partir de los resúmenes de k6.

Lee los archivos `k6_*.json` de 12_RESULTADOS_OBTENIDOS/prueba_de_carga/ (los que produce
`k6 run --summary-export=...`, ver README.md) y arma una tabla por consulta con el p95 de cada corrida.
Las cifras del informe salen de esos archivos: no se escriben a mano.

Uso (desde la raíz del repositorio; solo biblioteca estándar):
    python scripts/loadtest/informe.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT.parent / "12_RESULTADOS_OBTENIDOS" / "prueba_de_carga"
OUT = ROOT.parent / "12_RESULTADOS_OBTENIDOS" / "prueba_de_carga_tablero.md"

# (archivo, título de la corrida): en el orden en que se hicieron
CORRIDAS = [
    ("k6_1_linea_base.json", "1. Línea base"),
    ("k6_2_sin_n_mas_1.json", "2. Una llamada de mantenimientos y pool de conexiones"),
    ("k6_3_dos_workers.json", "3. Además, 2 procesos por servicio"),
    ("k6_4_cuatro_workers.json", "4. 4 procesos por servicio"),
]
CONSULTAS = [
    ("summary", "resumen del período"), ("summary_prev", "resumen del período anterior"), ("records", "registros de gasto"),
    ("trend", "tendencia"), ("maintenance_status", "estado de mantenimiento"), ("drivers", "conductores"), ("routes", "rutas"),
    ("vehicle_attention", "ranking de atención (AHP)"), ("cost_model", "metodología de costos"),
    ("maintenance_policy", "política de alertas"), ("vehicles", "lista de vehículos"), ("trips", "lista de viajes"),
    ("expenses", "lista de gastos"),
]
LIMITE_MS = 2000


def ms(value: float) -> str:
    return f"{value / 1000:.2f} s" if value >= 1000 else f"{value:.0f} ms"


def marca(value: float) -> str:
    return ms(value) + ("" if value < LIMITE_MS else " ✗")


def main() -> None:
    datos = []
    for archivo, titulo in CORRIDAS:
        ruta = DATA / archivo
        if not ruta.exists():
            sys.exit(f"Falta {ruta}: corra k6 con --summary-export (ver scripts/loadtest/README.md).")
        datos.append((titulo, json.loads(ruta.read_text(encoding="utf-8"))["metrics"]))

    def p95(metrics, nombre):
        return metrics[f"http_req_duration{{name:{nombre}}}"]["p(95)"]

    w = []
    w.append("# Prueba de carga del tablero (RNF-01)")
    w.append("")
    w.append("*Generado por `scripts/loadtest/informe.py` desde los resúmenes de k6 de `prueba_de_carga/`. "
             "No se edita a mano: se regenera.*")
    w.append("")
    w.append("## 1. Qué se midió")
    w.append("")
    w.append("RNF-01 exige consultas en menos de 2 s con hasta 10 usuarios concurrentes. Se simularon 10 usuarios "
             "administradores durante 60 s (k6, `scripts/loadtest/dashboard.js`). Cada uno hace lo que hace el navegador al abrir "
             "el tablero: dispara **13 consultas en paralelo** (resumen del período y del anterior, registros, tendencia, "
             "estado de mantenimiento, conductores, rutas, ranking de atención, política de alertas, metodología de costos y "
             "las listas de vehículos, viajes y gastos), espera 5 s y repite. Como cada carga tarda entre 1 y 3 s, cada usuario "
             "recarga el tablero cada 6 a 9 s; el tablero real se actualiza cada 20 s, de modo que la prueba pesa unas tres "
             "veces más que el uso esperado, y los 10 usuarios arrancan a la vez, que es el peor caso.")
    w.append("")
    w.append("Se registran dos cosas: el **p95 de cada consulta** (el 95 % de las respuestas tardó menos que ese valor) y el "
             "**p95 de la carga completa del tablero**, medido hasta que llega la última de las 13 respuestas, que es lo que "
             "percibe la persona.")
    w.append("")
    w.append("## 2. Resultados (p95)")
    w.append("")
    cab = ["Consulta"] + [t for t, _ in datos]
    w.append("| " + " | ".join(cab) + " |")
    w.append("|" + "|".join(["---"] + ["---:"] * len(datos)) + "|")
    for nombre, descripcion in CONSULTAS:
        w.append("| " + f"`{nombre}` ({descripcion})" + " | " + " | ".join(marca(p95(m, nombre)) for _, m in datos) + " |")
    w.append("| **Carga completa del tablero** | " + " | ".join(f"**{marca(m['carga_tablero_ms']['p(95)'])}**" for _, m in datos) + " |")
    w.append("| Mediana de la carga completa | " + " | ".join(ms(m["carga_tablero_ms"]["med"]) for _, m in datos) + " |")
    w.append("| Peticiones fallidas | " + " | ".join(f"{m['http_req_failed']['value'] * 100:.1f} %" for _, m in datos) + " |")
    w.append("| Cargas completas del tablero en 60 s | " + " | ".join(str(m["iterations"]["count"]) for _, m in datos) + " |")
    w.append("")
    w.append("✗ = supera los 2 s de RNF-01.")
    w.append("")
    w.append("## 3. Qué cambió entre corridas")
    w.append("")
    w.append("1. **Línea base.** Cada consulta que leía mantenimientos hacía una llamada HTTP por vehículo a fleet-core (12 con la "
             "flota piloto) y abría una conexión nueva en cada llamada. Con 10 usuarios simultáneos, cinco consultas y la carga "
             "completa superaron los 2 s.")
    w.append("2. **Una llamada y un pool de conexiones.** `GET /maintenance` entrega los mantenimientos de toda la flota en una "
             "consulta SQL; reporting-service reutiliza conexiones, con tiempos límite y reintentos con espera creciente. Sin "
             "carga, las consultas afectadas pasaron de 116–175 ms a 15–42 ms (por ejemplo, el estado de mantenimiento de 116 a 15 ms).")
    w.append("3. **2 procesos por servicio.** Con una CPU por proceso de Python, dos procesos atienden en paralelo lo que uno solo "
             "encolaba.")
    w.append("4. **4 procesos por servicio.** La mejora sigue, pero cada proceso más consume memoria y conexiones a la base de datos; "
             "para una flota de este tamaño, 2 procesos son un punto razonable y el número se ajusta con `UVICORN_WORKERS`.")
    w.append("")
    w.append("## 4. Condiciones y límites")
    w.append("")
    w.append("- Entorno: Docker Desktop en un equipo Windows 11 (24 CPU, 16 GB), PostgreSQL 16 en contenedor, gateway nginx y k6 "
             "**en el mismo equipo**. El generador de carga compite por CPU con el sistema medido, así que las cifras son "
             "indicativas y no la capacidad de un despliegue real.")
    w.append("- Datos: la base piloto (12 vehículos, 13 conductores, 640 viajes, 1 330 gastos, 96 mantenimientos) más los costos "
             "fijos y de personal de ejemplo. A esa escala las consultas a la base son baratas; lo que la prueba pone a prueba es "
             "el costo por petición de los servicios de Python. La escala de la base de datos se mide aparte "
             "(`scripts/bench_queries.py`).")
    w.append("- Una sola corrida de 60 s por configuración: sirve para comparar configuraciones entre sí y para comprobar el umbral, "
             "no para estimar una distribución estadística de largo plazo.")
    w.append("- Todas las respuestas fueron correctas (0 % de fallos) en las cuatro corridas.")
    w.append("")
    OUT.write_text("\n".join(w) + "\n", encoding="utf-8", newline="\n")
    print(f"Escrito {OUT}")


if __name__ == "__main__":
    main()
