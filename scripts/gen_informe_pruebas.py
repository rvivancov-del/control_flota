"""Genera 12_RESULTADOS_OBTENIDOS/pruebas_avance2.md desde los JUnit XML de las tres suites.

Los XML los escribe pytest (`--junitxml`) al correr cada suite completa —unitarias e integración— contra la
pila de verificación (ver scripts/README.md, "Pila de verificación aislada"):

    docker run --rm -e FLOTA_BASE_URL=http://host.docker.internal:18080/api \\
      -v "$PWD/services/<servicio>:/app" -v "$PWD/../12_RESULTADOS_OBTENIDOS/pruebas:/out" -w /app \\
      python:3.12-slim sh -c "pip install -q -r requirements.txt -r requirements-test.txt httpx==0.27.2 && \\
      python -m pytest tests -q --junitxml=/out/junit_<servicio>.xml -o junit_family=xunit2"
    python scripts/gen_informe_pruebas.py

El informe no se edita a mano: la cifra que cite el documento sale de aquí.
"""
import ast
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT.parent / "12_RESULTADOS_OBTENIDOS"
XML_DIR = RES / "pruebas"
OUT = RES / "pruebas_avance2.md"
SERVICIOS = ["auth-service", "fleet-core-service", "reporting-service"]


def descripcion_modulo(servicio: str, modulo: str) -> str:
    """Primera línea del docstring del archivo de pruebas (lo que verifica)."""
    ruta = ROOT / "services" / servicio / "tests" / f"{modulo}.py"
    if not ruta.exists():
        return ""
    doc = ast.get_docstring(ast.parse(ruta.read_text(encoding="utf-8"))) or ""
    return " ".join(doc.strip().split("\n\n")[0].split())


def leer(servicio: str) -> dict:
    ruta = XML_DIR / f"junit_{servicio}.xml"
    if not ruta.exists():
        sys.exit(f"Falta {ruta}: corra la suite con --junitxml primero (ver la cabecera de este script).")
    raiz = ET.parse(ruta).getroot()
    suite = raiz if raiz.tag == "testsuite" else raiz.find("testsuite")
    por_archivo = defaultdict(lambda: {"total": 0, "ok": 0, "fallas": 0, "omitidas": 0})
    fallidas = []
    for caso in suite.iter("testcase"):
        modulo = caso.get("classname", "").split(".")
        modulo = next((m for m in modulo if m.startswith("test_")), ".".join(modulo))
        d = por_archivo[modulo]
        d["total"] += 1
        if caso.find("failure") is not None or caso.find("error") is not None:
            d["fallas"] += 1
            fallidas.append(f"{modulo}::{caso.get('name')}")
        elif caso.find("skipped") is not None:
            d["omitidas"] += 1
        else:
            d["ok"] += 1
    return {
        "tests": int(suite.get("tests")), "fallas": int(suite.get("failures")) + int(suite.get("errors")),
        "omitidas": int(suite.get("skipped")), "tiempo": float(suite.get("time")),
        "fecha": suite.get("timestamp"), "por_archivo": dict(sorted(por_archivo.items())), "fallidas": fallidas,
    }


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> None:
    datos = {s: leer(s) for s in SERVICIOS}
    total = sum(d["tests"] for d in datos.values())
    fallas = sum(d["fallas"] for d in datos.values())
    omitidas = sum(d["omitidas"] for d in datos.values())
    aprobadas = total - fallas - omitidas
    fechas = sorted(d["fecha"] for d in datos.values() if d["fecha"])
    fecha = datetime.fromisoformat(fechas[0]).strftime("%Y-%m-%d %H:%M") if fechas else "sin fecha"

    w = ["# Evidencia de pruebas del prototipo", "",
         "*Generado por `sistema-control-flota/scripts/gen_informe_pruebas.py` desde los JUnit XML de "
         "`pruebas/`. No se edita a mano: se regenera.*", "",
         "## 1. Ejecución", "",
         f"- Fecha de la ejecución: {fecha} (hora del contenedor, UTC).",
         f"- Versión del código: rama `{git('branch', '--show-current')}`, commit `{git('rev-parse', '--short', 'HEAD')}`.",
         "- Entorno: pila de verificación aislada con Docker Compose (base de datos propia cargada con la base "
         "piloto ficticia de 12 vehículos, 13 conductores, 640 viajes, 1.330 gastos y 96 mantenimientos), "
         "gateway en el puerto 18080; cada suite corre en un contenedor `python:3.12-slim` desechable.",
         "- Alcance: pruebas unitarias (lógica en el mismo proceso) y de integración (`test_*_smoke.py`, "
         "peticiones HTTP reales a través del gateway, con autenticación y roles).", "",
         "## 2. Resultado", "",
         f"**{total} pruebas: {aprobadas} aprobadas, {fallas} fallidas, {omitidas} omitidas.**", "",
         "| Servicio | Pruebas | Aprobadas | Fallidas | Omitidas | Duración |",
         "|---|---:|---:|---:|---:|---:|"]
    for s in SERVICIOS:
        d = datos[s]
        w.append(f"| `{s}` | {d['tests']} | {d['tests'] - d['fallas'] - d['omitidas']} | {d['fallas']} | "
                 f"{d['omitidas']} | {d['tiempo']:.0f} s |")
    w.append(f"| **Total** | **{total}** | **{aprobadas}** | **{fallas}** | **{omitidas}** | "
             f"{sum(d['tiempo'] for d in datos.values()):.0f} s |")
    w += ["", "Las pruebas omitidas son opcionales por diseño (por ejemplo, la que agota el límite de "
          "peticiones del gateway solo corre con `RUN_RATE_LIMIT_TESTS=1`, porque bloquea el gateway un minuto).", ""]
    if fallas:
        w += ["### Pruebas fallidas", ""] + [f"- `{s}`: `{f}`" for s in SERVICIOS for f in datos[s]["fallidas"]] + [""]

    w += ["## 3. Detalle por archivo de pruebas", ""]
    for s in SERVICIOS:
        w += [f"### `{s}`", "", "| Archivo | Tipo | Pruebas | Aprobadas | Qué verifica |", "|---|---|---:|---:|---|"]
        for modulo, d in datos[s]["por_archivo"].items():
            tipo = "Integración" if modulo.endswith("_smoke") else "Unitaria"
            w.append(f"| `{modulo}.py` | {tipo} | {d['total']} | {d['ok']} | {descripcion_modulo(s, modulo)} |")
        w.append("")

    w += ["## 4. Otras mediciones del prototipo", "",
          "| Medición | Resultado | Informe |", "|---|---|---|",
          "| Cobertura de las pruebas unitarias | ver informe (umbral de RNF-07: 60 %) | `cobertura_pruebas.md` |",
          "| Prueba de carga del tablero (k6, 10 usuarios) | ver informe (meta de RNF-01: p95 < 2 s) | `prueba_de_carga_tablero.md` |",
          "| Benchmark de consultas a 10³, 10⁵ y 10⁶ viajes | ver informe | `benchmark_consultas.md` |",
          "| Sensibilidad del ranking AHP | ver informe | `ahp_sensibilidad_provisional.md` |", ""]
    OUT.write_text("\n".join(w) + "\n", encoding="utf-8", newline="\n")
    print(f"Escrito {OUT} — {total} pruebas, {aprobadas} aprobadas, {fallas} fallidas, {omitidas} omitidas")


if __name__ == "__main__":
    main()
