"""Genera 12_RESULTADOS_OBTENIDOS/modelo_de_costos_indicadores.md desde el código.

Las tablas "Indicador -> fórmula -> fuente -> código", la correspondencia con las ocho categorías de
Zysińska & Menes (2026) y las tarifas de IVA se leen de cost_model.py e iva_config.json, de modo que el
documento no puede quedar distinto de lo que el sistema calcula. El texto de reglas y límites es fijo.

Uso (desde la raíz del repositorio; solo biblioteca estándar):
    python scripts/gen_doc_modelo_costos.py            # escribe el documento
    python scripts/gen_doc_modelo_costos.py --check    # falla (código 1) si el documento no está al día
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTING = ROOT / "services" / "reporting-service"
OUT = ROOT.parent / "12_RESULTADOS_OBTENIDOS" / "modelo_de_costos_indicadores.md"

sys.path.insert(0, str(REPORTING))
from app.dashboards import cost_model as cm  # noqa: E402  (importa solo la biblioteca estándar)

IVA = json.loads((REPORTING / "app" / "dashboards" / "iva_config.json").read_text(encoding="utf-8"))

ITEM_LABEL = {
    "combustible": "Combustible", "peaje": "Peajes", "alimentacion": "Alimentación (viáticos del conductor)",
    "mantenimiento": "Mantenimiento", "depreciacion": "Depreciación", "capital": "Capital (crédito o leasing)",
    "seguro": "Seguro del vehículo", "impuestos": "Impuestos y matrícula", "otros": "Otros costos fijos",
    "personal": "Sueldo y beneficios sociales del conductor",
}
WHERE_RECORDED = {
    "combustible": "gastos del viaje (`expenses`)", "peaje": "gastos del viaje (`expenses`)",
    "alimentacion": "gastos del viaje (`expenses`)", "mantenimiento": "mantenimientos (`maintenance_records`)",
    "depreciacion": "costos fijos (`fixed_costs`)", "capital": "costos fijos (`fixed_costs`)",
    "seguro": "costos fijos (`fixed_costs`)", "impuestos": "costos fijos (`fixed_costs`)",
    "otros": "costos fijos (`fixed_costs`)", "personal": "costos de personal (`personnel_costs`)",
}
BEHAVIOR = {"variable": "variable", "fija": "fija", "mixta": "variable y fija"}


def md_row(*cells: str) -> str:
    return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"


def build() -> str:
    lines: list[str] = []
    w = lines.append
    w("# Modelo de costos e indicadores del prototipo")
    w("")
    w("*Documento generado por `scripts/gen_doc_modelo_costos.py` a partir de `cost_model.py` e `iva_config.json`. "
      "No se edita a mano: se regenera.*")
    w("")
    w("## 1. Alcance")
    w("")
    w("El prototipo original registraba solo costos variables por viaje (combustible, peajes y alimentación) y "
      "de mantenimiento. La literatura revisada separa el costo total en una parte variable y otra fija "
      "(Poliak et al., 2025) y estructura el costo de un vehículo-kilómetro en ocho categorías (Zysińska & "
      "Menes, 2026). Sin depreciación, capital, seguros, impuestos ni personal, los costos por kilómetro y el "
      "margen no son calculables. Este modelo incorpora esos rubros y calcula los indicadores de la sección 4.")
    w("")
    w("## 2. Rubros del prototipo y su comportamiento")
    w("")
    w(md_row("Rubro", "Comportamiento", "Categoría de Zysińska & Menes (2026)", "Dónde se registra"))
    w(md_row("---", "---", "---", "---"))
    for item in cm.ALL_ITEMS:
        behavior = "variable" if item in cm.VARIABLE_ITEMS else "fijo"
        w(md_row(ITEM_LABEL[item], behavior, cm.CATEGORY_LABEL[cm.ITEM_CATEGORY[item]], WHERE_RECORDED[item]))
    w("")
    w("La alimentación se clasifica como variable porque depende de los viajes, y dentro de la categoría de "
      "conductores porque son sus viáticos: la categoría de Zysińska & Menes incluye la remuneración, los "
      "gastos de viaje y la seguridad social del conductor.")
    w("")
    w("## 3. Correspondencia con las ocho categorías")
    w("")
    w(md_row("Categoría", "Rubros del prototipo", "Comportamiento"))
    w(md_row("---", "---", "---"))
    for entry in cm.category_map():
        items = ", ".join(ITEM_LABEL[i].split(" (")[0].lower() for i in entry["items"]) or "sin rubro"
        w(md_row(entry["label"], items, BEHAVIOR[entry["behavior"]]))
    w("")
    w("## 4. Indicadores: fórmula, fuente y código")
    w("")
    w(md_row("Indicador", "Nombre", "Fórmula", "Fuente", "Dónde se calcula"))
    w(md_row("---", "---", "---", "---", "---"))
    for ind in cm.INDICATORS:
        w(md_row(f"`{ind.id}`", ind.name, ind.formula, ind.source, f"`{ind.where}`"))
    w("")
    w("Notación: Cv, Cf y Ct son los costos variable, fijo y total del período; M, los kilómetros de los viajes "
      "completados; R, el ingreso de esos viajes; PC, los costos de personal.")
    w("")
    w("## 5. Reglas de cálculo")
    w("")
    w("- **Prorrateo por días.** Un costo fijo se registra como monto mensual o anual con su vigencia. Su "
      "devengo diario es el monto mensual × 12 / 365, o el anual / 365, por los días en que la vigencia se "
      "solapa con el período (ambos extremos incluidos). Se usa la convención de 365 días también en años "
      "bisiestos; el redondeo a centavos se hace una sola vez, al agregar.")
    w("- **Personal por vehículo.** El costo de cada conductor se reparte entre los vehículos que condujo en "
      "proporción a sus kilómetros con cada uno. Un conductor con costo pero sin kilómetros en el período no "
      "tiene a qué vehículo cargarse: su costo queda *sin asignar*, se suma al total de la flota y se informa "
      "aparte; no se muestra al filtrar un solo vehículo.")
    w("- **Margen de contribución y utilidad.** El margen de contribución (R − Cv) es visible sin conocer los "
      "costos fijos; la utilidad (R − Ct) y el margen (utilidad / R) exigen el costo total. El ingreso solo "
      "existe en los viajes completados que lo registran; el sistema informa el porcentaje de kilómetros con "
      "ingreso registrado, porque por debajo de 100 % el margen queda subestimado.")
    w("- **Filtro por categoría.** El filtro de categoría acota el gasto mostrado, pero no el margen: el "
      "margen se calcula siempre sobre el costo completo, para que no cambie al mirar solo el combustible.")
    w("- **Período comparable.** Un período en curso se compara con los mismos días del período anterior, no "
      "con el período anterior completo. La proyección de cierre es una estimación lineal (heurística); su "
      "rango usa solo períodos completos.")
    w("- **IVA.** El interruptor `iva_mode` elige entre montos pagados (`bruto`, por defecto) y montos sin "
      "IVA (`neto` = monto / (1 + tarifa del rubro)). Las tarifas provisionales vigentes son:")
    w("")
    w(md_row("Rubro", "Tarifa"))
    w(md_row("---", "---"))
    for key, rate in IVA["tarifas"].items():
        w(md_row(key, f"{rate * 100:.0f} %"))
    w("")
    w(f"  Estado: `{IVA['estado']}` (versión `{IVA['version']}`). {IVA['procedencia']}")
    w("")
    w("## 6. Visibilidad por rol")
    w("")
    w(md_row("Dato", "Administrador", "Operador"))
    w(md_row("---", "---", "---"))
    w(md_row("Costos variables, margen de contribución y costo variable por km", "sí", "sí"))
    w(md_row("Costos fijos y de personal, Ct, utilidad, margen, LP y ROP", "sí", "no"))
    w(md_row("Personal por conductor y edición de costos fijos", "sí", "no"))
    w(md_row("Exportación a Excel y PDF", "sí", "no"))
    w("")
    w("## 7. Ejemplo calculado a mano")
    w("")
    w("Período de 30 días y 1 000 km. Cv = combustible 300 + peajes 50 + alimentación 40 + mantenimiento 110 = "
      "500. Cf = depreciación 150 + capital 50 + seguro 60 + impuestos 20 + otros 20 + personal 200 = 500. "
      "Ct = 1 000 y R = 1 250.")
    w("")
    w(md_row("Indicador", "Cálculo", "Resultado"))
    w(md_row("---", "---", "---"))
    w(md_row("cv, cf, ct", "500 / 1 000; 500 / 1 000; 1 000 / 1 000", "0,50; 0,50; 1,00 USD/km"))
    w(md_row("Ingreso por km", "1 250 / 1 000", "1,25 USD/km"))
    w(md_row("Utilidad y margen", "1 250 − 1 000; 250 / 1 250", "250 USD; 20 %"))
    w(md_row("Margen de contribución", "1 250 − 500", "750 USD"))
    w(md_row("LP y ROP", "1 250 / 200; 250 / 200 × 100", "6,25; 125 %"))
    w("")
    w("Este caso está automatizado en `services/reporting-service/tests/test_cost_model.py`; el reparto del "
      "personal, el prorrateo por días, el IVA neto y los sesgos corregidos tienen su propia prueba con "
      "cálculo manual en `test_costs_service.py` y `fleet-core-service/tests/test_costos.py`.")
    w("")
    w("## 8. Límites y supuestos declarados")
    w("")
    w("- Las tarifas de IVA son provisionales: no las ha confirmado un contador ni el SRI. Mientras tanto, el "
      "modo por defecto es `bruto` y las cifras sin IVA deben leerse como provisionales.")
    w("- ROA y ROE (Kutac et al., 2022, ecs. 2 y 3) no se calculan: exigen un balance general, que el "
      "prototipo no registra. Se calculan LP y ROP, que solo necesitan ingreso, costo y personal.")
    w("- Los costos fijos y de personal los registra el administrador; el sistema no los obtiene de la "
      "contabilidad. Si faltan, el costo total queda subestimado y la pantalla lo advierte.")
    w("- La base piloto no trae costos fijos ni de personal. Los que carga `scripts/seed_costos_ejemplo.py` son "
      "ilustrativos, llevan la palabra EJEMPLO en sus notas y no corresponden a ninguna empresa.")
    w("- La depreciación es lineal en el tiempo, no por kilómetro. La convención de 365 días introduce una "
      "diferencia menor a 0,3 % en años bisiestos.")
    w("- El reparto del personal por kilómetros conducidos es una regla de asignación del prototipo, no de las "
      "fuentes; otra regla (por días asignados, por ejemplo) daría otros costos por vehículo, aunque el "
      "total de la flota no cambia.")
    w("- Zysińska & Menes (2026) y Poliak et al. (2025) estudian transporte de carga europeo; se adoptan su "
      "estructura de costos y sus fórmulas, no sus valores.")
    w("- La Tabla 3 de Poliak et al. (2025) rotula la energía eléctrica como costo fijo, aunque su texto la trata "
      "como costo variable. El prototipo sigue el texto: el combustible es un costo variable, que crece con los "
      "kilómetros.")
    w("")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="solo comprueba que el documento esté al día")
    args = ap.parse_args()
    text = build()
    if args.check:
        current = OUT.read_text(encoding="utf-8").replace("\r\n", "\n") if OUT.exists() else None
        if current != text:
            print(f"{OUT} no está al día: ejecute scripts/gen_doc_modelo_costos.py", file=sys.stderr)
            sys.exit(1)
        print("El documento está al día.")
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Escrito {OUT} ({len(text.splitlines())} líneas).")


if __name__ == "__main__":
    main()
