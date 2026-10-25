"""Reúne en un solo JSON todas las cifras que cita el documento del Avance 2.

Fuente única de verdad para el documento (_automatizacion/build_avance2.py las inserta) y para la verificación
(verificar_coherencia.py del plugin del Asesor compara cada cifra con el texto). Nada se escribe a mano: todo se
lee de los artefactos de 12_RESULTADOS_OBTENIDOS/ o se calcula con el código del prototipo.

    python scripts/gen_cifras_avance2.py            # escribe ../12_RESULTADOS_OBTENIDOS/cifras_avance2.json
    python scripts/gen_cifras_avance2.py --check    # falla si el JSON guardado no coincide con lo recalculado
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT.parent / "12_RESULTADOS_OBTENIDOS"
OUT = RES / "cifras_avance2.json"
SERVICIOS = ["auth-service", "fleet-core-service", "reporting-service"]

sys.path.insert(0, str(ROOT / "services" / "reporting-service"))
from app.dashboards import ahp, ahp_analysis  # noqa: E402


def entero(x: float) -> int:
    """Redondeo comercial (0,5 sube), el de los informes; round() de Python redondea 68,5 a 68."""
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pruebas() -> dict:
    por_servicio, tot = {}, {"total": 0, "aprobadas": 0, "fallidas": 0, "omitidas": 0}
    for s in SERVICIOS:
        raiz = ET.parse(RES / "pruebas" / f"junit_{s}.xml").getroot()
        suite = raiz if raiz.tag == "testsuite" else raiz.find("testsuite")
        n = int(suite.get("tests"))
        fall = int(suite.get("failures")) + int(suite.get("errors"))
        omit = int(suite.get("skipped"))
        d = {"total": n, "aprobadas": n - fall - omit, "fallidas": fall, "omitidas": omit,
             "segundos": round(float(suite.get("time")), 1)}
        por_servicio[s] = d
        for k in tot:
            tot[k] += d[k]
    cabecera = (RES / "pruebas_avance2.md").read_text(encoding="utf-8")
    fecha = re.search(r"Fecha de la ejecución: (\d{4}-\d{2}-\d{2})", cabecera).group(1)
    commit = re.search(r"commit `([0-9a-f]+)`", cabecera).group(1)
    return {**tot, "por_servicio": por_servicio, "fecha": fecha, "commit": commit}


def cobertura() -> dict:
    por, cub, val = {}, 0, 0
    for s in SERVICIOS:
        r = ET.parse(RES / "coverage" / f"coverage_{s}.xml").getroot()
        lc, lv, bc, bv = (int(r.get(k) or 0) for k in ("lines-covered", "lines-valid", "branches-covered", "branches-valid"))
        por[s] = round(100 * (lc + bc) / (lv + bv), 1)  # líneas + ramas, la fórmula del resumen de coverage.py
        cub += lc + bc
        val += lv + bv
    return {"total": entero(100 * cub / val), "por_servicio": por,
            "minimo": entero(min(por.values())), "maximo": entero(max(por.values()))}


def carga() -> dict:
    def p95(nombre):
        d = json.loads((RES / "prueba_de_carga" / f"{nombre}.json").read_text(encoding="utf-8"))
        return round(d["metrics"]["carga_tablero_ms"]["p(95)"] / 1000, 2)
    return {"p95_base": p95("k6_1_linea_base"), "p95": p95("k6_3_dos_workers"), "p95_cuatro": p95("k6_4_cuatro_workers"),
            "usuarios": 10, "segundos": 60}


def benchmark() -> dict:
    d = json.loads((RES / "benchmark" / "escala_1000000.json").read_text(encoding="utf-8"))
    sin, con = d["sin_indices"]["consultas"], d["con_indices"]["consultas"]
    puntuales = ["viajes de un vehículo (mes)", "gastos de un vehículo (mes)", "gastos de un viaje"]
    mejoras = {q: round(sin[q]["mediana_ms"] / con[q]["mediana_ms"], 1) for q in puntuales}
    return {"viajes": d["viajes"], "mejora_min": min(mejoras.values()), "mejora_max": max(mejoras.values()),
            "mejoras": mejoras, "agregado_anual_max_s": round(con["gastos agregados (año)"]["mediana_ms"] / 1000, 1)}


def ahp_cifras() -> dict:
    cfg = ahp.CONFIG
    m = cfg.matrix
    n = len(m)
    sumas = [sum(m[i][j] for i in range(n)) for j in range(n)]
    norm = [[m[i][j] / sumas[j] for j in range(n)] for i in range(n)]
    w = [sum(f) / n for f in norm]
    aw = [sum(m[i][j] * w[j] for j in range(n)) for i in range(n)]
    coc = [aw[i] / w[i] for i in range(n)]
    lam = sum(coc) / n
    ic = (lam - n) / (n - 1)
    pesos = ahp.compute_ahp_weights()
    assert abs(pesos.consistency_ratio - ic / ahp.RANDOM_INDEX[n]) < 1e-12, "el cálculo independiente no coincide con ahp.py"
    filas = ahp_analysis.sensitivity(ahp_analysis.standard_item_set())
    return {"estado": cfg.estado, "version": cfg.version, "procedencia": cfg.procedencia,
            "criterios": list(ahp.CRITERIA), "matriz": m, "sumas_columna": sumas, "normalizada": norm,
            "pesos": dict(zip(ahp.CRITERIA, w, strict=True)), "aw": aw, "cocientes": coc, "lambda_max": lam, "ic": ic,
            "ia": ahp.RANDOM_INDEX[n], "cr": pesos.consistency_ratio, "umbral": ahp.CONSISTENCY_LIMIT,
            "criticidad": cfg.criticidad_seguridad, "costo_direccion": cfg.costo.direccion,
            "urgencia": {"sin_urgencia_multiplo": cfg.urgencia.sin_urgencia_multiplo,
                         "puntaje_en_proximo": cfg.urgencia.puntaje_en_proximo,
                         "puntaje_sin_kilometraje": cfg.urgencia.puntaje_sin_kilometraje},
            "tau_min": round(min(r.tau for r in filas), 3),
            "top1_estable": all(r.top1_same for r in filas)}


def politica() -> dict:
    p = json.loads((ROOT / "services/fleet-core-service/app/maintenance/maintenance_policy.json").read_text(encoding="utf-8"))
    return {"estado": p["estado"], "proximo_km": p["proximo_km"], "por_tipo": p["proximo_km_por_tipo"]}


def calcular() -> dict:
    return {"pruebas": pruebas(), "cobertura": cobertura(), "carga": carga(), "benchmark": benchmark(),
            "ahp": ahp_cifras(), "politica": politica()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    datos = calcular()
    texto = json.dumps(datos, indent=1, ensure_ascii=False) + "\n"
    if a.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != texto:
            print(f"{OUT.name} no coincide con lo recalculado: vuelve a generarlo.")
            return 1
        print(f"{OUT.name}: al día.")
        return 0
    OUT.write_text(texto, encoding="utf-8")
    print(f"Escrito {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
