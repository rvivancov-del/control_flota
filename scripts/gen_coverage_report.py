"""Genera 12_RESULTADOS_OBTENIDOS/cobertura_pruebas.md desde los coverage_<servicio>.xml (formato
Cobertura, el que escribe `pytest --cov-report=xml`).

Las cifras de cobertura del documento salían de una frase suelta en el README ("71-82% por servicio, 78%
combinado"), sin ningún artefacto que la respaldara (matriz de trazabilidad, fila N-06: SIN EVIDENCIA).
Este script lee los XML que sí genera `pytest-cov` y escribe el informe desde ahí: la cifra que cita el
documento y la que produce la herramienta son, por construcción, la misma.

El "% cubierto" combina líneas y ramas con la misma fórmula que usa `coverage.py` en su resumen de
terminal: (líneas cubiertas + ramas cubiertas) / (líneas totales + ramas totales).

Uso (desde la raíz del repositorio; solo biblioteca estándar):
    # 1) generar los XML (pruebas UNITARIAS, sin el stack: -m "not smoke")
    docker run --rm -v "$PWD/services/<servicio>:/app" -v "$PWD/12_RESULTADOS_OBTENIDOS/coverage:/out" \\
      -w /app python:3.12-slim sh -c \\
      "pip install -q -r requirements.txt -r requirements-test.txt && \\
       python -m pytest tests -m 'not smoke' -q --cov=app --cov-report=xml:/out/coverage_<servicio>.xml"
    # 2) regenerar el informe
    python scripts/gen_coverage_report.py

Las pruebas de integración (test_*_smoke.py, marcadas "smoke" por tests/conftest.py) quedan fuera a
propósito: corren la aplicación dentro de OTRO proceso (el stack, por HTTP), así que `coverage.py` no
puede verlas — para esos módulos (routers simples verificados de punta a punta) la cobertura real es
mayor que la que aquí se mide; ver la sección de límites del informe.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XML_DIR = ROOT.parent / "12_RESULTADOS_OBTENIDOS" / "coverage"
OUT = ROOT.parent / "12_RESULTADOS_OBTENIDOS" / "cobertura_pruebas.md"
UMBRAL_RNF07 = 60

SERVICIOS = ["auth-service", "fleet-core-service", "reporting-service"]


def leer(servicio: str) -> dict:
    ruta = XML_DIR / f"coverage_{servicio}.xml"
    if not ruta.exists():
        sys.exit(f"Falta {ruta}: genere los XML de cobertura primero (ver la cabecera de este script).")
    root = ET.parse(ruta).getroot()
    lv, lc = int(root.get("lines-valid")), int(root.get("lines-covered"))
    bv, bc = int(root.get("branches-valid")), int(root.get("branches-covered"))
    cubierto = (lc + bc) / (lv + bv) * 100 if (lv + bv) else 0.0
    # Archivos con menos cobertura, para señalar qué falta (casi siempre routers CRUD, cubiertos por
    # los smoke, no por las unitarias).
    peores = []
    for clase in root.iter("class"):
        lineas = clase.findall("./lines/line")
        total = len(lineas)
        if total == 0:
            continue
        cubiertas = sum(1 for ln in lineas if ln.get("hits") != "0")
        pct = cubiertas / total * 100
        peores.append((clase.get("filename"), pct, total))
    peores.sort(key=lambda x: x[1])
    return {"lines_valid": lv, "lines_covered": lc, "branches_valid": bv, "branches_covered": bc,
            "cubierto": cubierto, "peores": peores}


def main() -> None:
    datos = {s: leer(s) for s in SERVICIOS}
    lv = sum(d["lines_valid"] for d in datos.values())
    lc = sum(d["lines_covered"] for d in datos.values())
    bv = sum(d["branches_valid"] for d in datos.values())
    bc = sum(d["branches_covered"] for d in datos.values())
    combinado = (lc + bc) / (lv + bv) * 100 if (lv + bv) else 0.0

    w = []
    w.append("# Cobertura de las pruebas unitarias")
    w.append("")
    w.append("*Generado por `scripts/gen_coverage_report.py` desde `coverage/coverage_<servicio>.xml` "
             "(`pytest-cov`). No se edita a mano: se regenera.*")
    w.append("")
    w.append("## 1. Qué mide y qué no")
    w.append("")
    w.append("Cobertura de línea y de rama de las pruebas **unitarias** (`pytest -m \"not smoke\"`), que no "
             "necesitan el stack levantado: importan `app.*` en el mismo proceso y `coverage.py` puede "
             "instrumentarlas. El porcentaje combina líneas y ramas cubiertas sobre el total, la misma "
             "fórmula que usa `coverage.py` en su resumen de terminal.")
    w.append("")
    w.append("Las pruebas de integración (`test_*_smoke.py`, marcadas `smoke` automáticamente por "
             "`tests/conftest.py` según el nombre del archivo) quedan **fuera** de esta cifra: corren "
             "contra el stack real por HTTP, en otro proceso, así que `coverage.py` no las ve. Varios "
             "routers CRUD simples (por ejemplo `expenses/router.py`, `trips/router.py`, "
             "`vehicles/router.py` en fleet-core-service) están verificados de punta a punta por esas "
             "pruebas y aparecen aquí con cobertura baja: la cifra de este informe subestima la cobertura "
             "real de esos archivos.")
    w.append("")
    w.append("## 2. Resultado")
    w.append("")
    w.append(f"**Combinado (los tres servicios): {combinado:.0f} %** — {'por encima' if combinado >= UMBRAL_RNF07 else 'por debajo'} "
             f"del {UMBRAL_RNF07} % de RNF-07.")
    w.append("")
    w.append("| Servicio | Cobertura | Líneas | Ramas | Umbral RNF-07 (60 %) |")
    w.append("|---|---:|---:|---:|:---:|")
    for s in SERVICIOS:
        d = datos[s]
        estado = "✅" if d["cubierto"] >= UMBRAL_RNF07 else "❌"
        w.append(f"| `{s}` | {d['cubierto']:.0f} % | {d['lines_covered']}/{d['lines_valid']} | "
                 f"{d['branches_covered']}/{d['branches_valid']} | {estado} |")
    w.append("")
    w.append("## 3. Archivos con menos cobertura por servicio")
    w.append("")
    w.append("Los tres archivos con menor cobertura de línea de cada servicio, casi siempre routers CRUD "
             "que la sección 1 explica: verificados por los smoke, no por las unitarias.")
    w.append("")
    for s in SERVICIOS:
        w.append(f"**{s}**")
        w.append("")
        w.append("| Archivo | Cobertura de línea |")
        w.append("|---|---:|")
        for archivo, pct, total in datos[s]["peores"][:3]:
            w.append(f"| `{archivo}` | {pct:.0f} % ({total} líneas) |")
        w.append("")
    w.append("## 4. Cómo reproducirlo")
    w.append("")
    w.append("```bash")
    w.append("for s in auth-service fleet-core-service reporting-service; do")
    w.append("  docker run --rm -v \"$PWD/services/$s:/app\" -v \"$PWD/../12_RESULTADOS_OBTENIDOS/coverage:/out\" \\")
    w.append("    -w /app python:3.12-slim sh -c \\")
    w.append("    \"pip install -q -r requirements.txt -r requirements-test.txt httpx==0.27.2 && \\")
    w.append("     python -m pytest tests -m 'not smoke' -q --cov=app --cov-report=term-missing --cov-report=xml:/out/coverage_$s.xml\"")
    w.append("done")
    w.append("python scripts/gen_coverage_report.py")
    w.append("```")
    w.append("")
    w.append("Las pruebas de integración (`-m smoke`) se corren aparte, contra la pila de verificación "
             "(ver `scripts/README.md`); no producen `coverage.xml` por la razón de la sección 1.")
    w.append("")
    OUT.write_text("\n".join(w) + "\n", encoding="utf-8", newline="\n")
    print(f"Escrito {OUT} — combinado {combinado:.0f} %")


if __name__ == "__main__":
    main()
