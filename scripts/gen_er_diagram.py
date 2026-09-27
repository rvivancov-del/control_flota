"""Genera el modelo entidad-relación y el diccionario de datos desde el esquema EN EJECUCIÓN (no a mano).

Lee information_schema y pg_constraint de la base viva (esquemas auth y fleet; solo lectura) y escribe en
08_DIAGRAMAS_MODELOS_Y_DISENO/avance2/:
    modelo_entidad_relacion.mmd   diagrama Mermaid (erDiagram)
    diccionario_de_datos.md       tablas, campos, tipo, nulos, claves, referencias y restricciones CHECK

Así el diagrama del documento y la base real coinciden por construcción. Con --check no escribe: compara lo
generado con los archivos existentes y termina con código 1 si difieren (el esquema cambió y hay que regenerar).

Uso (desde la raíz del repositorio, con `docker compose up`):
    python scripts/gen_er_diagram.py            # regenera
    python scripts/gen_er_diagram.py --check    # verifica que siguen al día
"""
import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT.parent / "08_DIAGRAMAS_MODELOS_Y_DISENO" / "avance2"
ESQUEMAS = ("auth", "fleet")
# Referencias lógicas entre esquemas: cada servicio es dueño de su esquema (infra/postgres/roles.sql), así que
# no puede haber llave foránea entre ellos; el identificador del usuario viaja en el JWT.
REFERENCIAS_LOGICAS = [("fleet", "trips", "created_by", "auth", "users", "id")]

TIPOS = {
    "character varying": "varchar", "timestamp with time zone": "timestamptz", "integer": "int",
    "numeric": "numeric", "uuid": "uuid", "boolean": "bool", "text": "text", "date": "date",
}


def psql(sql: str) -> list[list[str]]:
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "flota", "-d", "flota_db", "-At", "-F", "\t",
         "-v", "ON_ERROR_STOP=1", "-c", sql],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=False)
    if r.returncode != 0:
        sys.exit(f"Falló la consulta al esquema: {r.stderr.strip()}")
    return [ln.split("\t") for ln in r.stdout.splitlines() if ln]


def leer_esquema():
    lista = ",".join(f"'{e}'" for e in ESQUEMAS)
    columnas = psql(f"""
        select c.table_schema, c.table_name, c.column_name, c.data_type, c.is_nullable,
               coalesce(c.character_maximum_length::text, ''), coalesce(c.numeric_precision::text, ''),
               coalesce(c.numeric_scale::text, '')
        from information_schema.columns c
        join information_schema.tables t
          on t.table_schema = c.table_schema and t.table_name = c.table_name and t.table_type = 'BASE TABLE'
        where c.table_schema in ({lista}) and c.table_name <> 'alembic_version'
        order by 1, 2, c.ordinal_position""")
    claves = psql(f"""
        select tc.table_schema, tc.table_name, kcu.column_name, tc.constraint_type,
               coalesce(ccu.table_schema, ''), coalesce(ccu.table_name, ''), coalesce(ccu.column_name, '')
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
          on tc.constraint_name = kcu.constraint_name and tc.table_schema = kcu.table_schema
        left join information_schema.constraint_column_usage ccu
          on tc.constraint_type = 'FOREIGN KEY' and ccu.constraint_name = tc.constraint_name
        where tc.table_schema in ({lista}) and tc.table_name <> 'alembic_version'
          and tc.constraint_type in ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
        order by 1, 2, 3""")
    checks = psql(f"""
        select n.nspname, c.relname, pg_get_constraintdef(k.oid)
        from pg_constraint k join pg_class c on c.oid = k.conrelid join pg_namespace n on n.oid = c.relnamespace
        where k.contype = 'c' and n.nspname in ({lista})
        order by 1, 2, 3""")
    return columnas, claves, checks


def legible(definicion: str) -> str:
    """Quita los casts que agrega pg_get_constraintdef y convierte '= ANY (ARRAY[...])' en 'IN (...)'."""
    s = re.sub(r"::[a-z]+(?: [a-z]+)*(?:\[\])?", "", definicion)
    return re.sub(r"= ANY \(\(ARRAY\[(.*?)\]\)\)", r"IN (\1)", s)


def tipo(data_type: str, largo: str, precision: str, escala: str) -> str:
    base = TIPOS.get(data_type, data_type.replace(" ", "_"))
    if largo:
        return f"{base}({largo})"
    if data_type == "numeric" and precision:
        return f"numeric({precision},{escala or 0})"
    return base


def construir():
    columnas, claves, checks = leer_esquema()
    tablas = defaultdict(list)
    for esq, tab, col, dt, nul, largo, prec, esc in columnas:
        tablas[(esq, tab)].append({"col": col, "tipo": tipo(dt, largo, prec, esc), "nulo": nul == "YES"})
    pk, uk, fk = set(), set(), {}
    for esq, tab, col, ctype, fesq, ftab, fcol in claves:
        if ctype == "PRIMARY KEY":
            pk.add((esq, tab, col))
        elif ctype == "UNIQUE":
            uk.add((esq, tab, col))
        else:
            fk[(esq, tab, col)] = (fesq, ftab, fcol)
    chk = defaultdict(list)
    for esq, tab, definicion in checks:
        chk[(esq, tab)].append(legible(definicion))

    # ------------------------------------------------------------------ Mermaid
    ent = {k: f"{k[0]}_{k[1]}" for k in tablas}
    m = ["erDiagram"]
    for (esq, tab), cols in tablas.items():
        m.append(f'    {ent[(esq, tab)]}["{esq}.{tab}"] {{')
        for c in cols:
            k = (esq, tab, c["col"])
            marcas = [x for x, cond in (("PK", k in pk), ("FK", k in fk), ("UK", k in uk)) if cond]
            t = c["tipo"].replace("(", "_").replace(")", "").replace(",", "_")  # Mermaid: tipo sin paréntesis
            m.append(f"        {t} {c['col']}{(' ' + ','.join(marcas)) if marcas else ''}")
        m.append("    }")
    cols_por = {(e, t): {c["col"]: c for c in cols} for (e, t), cols in tablas.items()}
    for (esq, tab, col), (fesq, ftab, _fcol) in sorted(fk.items()):
        nulo = cols_por[(esq, tab)][col]["nulo"]
        m.append(f'    {ent[(fesq, ftab)]} {"|o" if nulo else "||"}--o{{ {ent[(esq, tab)]} : "{col}"')
    for esq, tab, col, fesq, ftab, _fcol in REFERENCIAS_LOGICAS:
        m.append(f'    {ent[(fesq, ftab)]} |o..o{{ {ent[(esq, tab)]} : "{col} (referencia lógica)"')
    mermaid = "\n".join(m) + "\n"

    # ------------------------------------------------------------------ diccionario
    d = ["# Diccionario de datos", "",
         "*Generado por `sistema-control-flota/scripts/gen_er_diagram.py` desde el esquema en ejecución (PostgreSQL). "
         "No se edita a mano: se regenera.*", "",
         f"Esquemas: {', '.join(ESQUEMAS)} — {len(tablas)} tablas (sin contar `alembic_version`). Cada esquema "
         "pertenece a un solo servicio y a su propio rol de base de datos (`infra/postgres/roles.sql`); por eso no "
         "hay llaves foráneas entre esquemas: la referencia de `fleet.trips.created_by` al usuario de `auth.users` "
         "es lógica (el identificador llega en el token JWT).", ""]
    for (esq, tab), cols in tablas.items():
        d += [f"## `{esq}.{tab}`", "", "| Campo | Tipo | Nulo | Clave | Referencia |", "|---|---|:---:|---|---|"]
        for c in cols:
            k = (esq, tab, c["col"])
            clave = ", ".join(x for x, cond in (("PK", k in pk), ("FK", k in fk), ("UK", k in uk)) if cond)
            ref = ".".join(fk[k]) if k in fk else next(
                (f"{fe}.{ft}.{fc} (lógica)" for e, t, cc, fe, ft, fc in REFERENCIAS_LOGICAS if (e, t, cc) == k), "")
            d.append(f"| `{c['col']}` | {c['tipo']} | {'sí' if c['nulo'] else 'no'} | {clave} | {ref} |")
        if chk[(esq, tab)]:
            d += ["", "Restricciones CHECK:", ""] + [f"- `{x}`" for x in chk[(esq, tab)]]
        d.append("")
    return mermaid, "\n".join(d)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="no escribe; falla si los archivos no están al día")
    args = ap.parse_args()
    mermaid, dicc = construir()
    salidas = {OUT_DIR / "modelo_entidad_relacion.mmd": mermaid, OUT_DIR / "diccionario_de_datos.md": dicc}
    if args.check:
        viejos = [p.name for p, txt in salidas.items() if not p.exists() or p.read_text(encoding="utf-8") != txt]
        if viejos:
            sys.exit(f"Desactualizados respecto del esquema en ejecución: {', '.join(viejos)}")
        print("Modelo ER y diccionario al día con el esquema en ejecución.")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p, txt in salidas.items():
        p.write_text(txt, encoding="utf-8", newline="\n")
        print("Escrito", p)


if __name__ == "__main__":
    main()
