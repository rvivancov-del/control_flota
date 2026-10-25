# scripts/

Utilidades de reproducibilidad. Se ejecutan **desde la raíz del repositorio** con
`docker compose up` corriendo. Solo usan la biblioteca estándar de Python.

## Base piloto reproducible

Las cifras del documento de tesis (12 vehículos, 13 conductores, 640 viajes, 1.330
gastos y 96 mantenimientos) salen de la base piloto de `fleet-core-service`. Los datos
son ficticios (placas, licencias y teléfonos de ejemplo).

| Script | Qué hace |
|---|---|
| `export_pilot_dataset.py` | Lee la base viva (`flota_db`, solo lectura) y escribe `seed/pilot_dataset.sql` y `seed/pilot_dataset.manifest.json` (conteos, sumas y hash SHA-256). Las columnas de credencial del QR de los conductores (token o hash, emisión, vigencia, último uso) **no** se exportan. |
| `seed_demo.py` | Recrea una base de demostración (por defecto `flota_seed`), crea el esquema `fleet`, aplica las migraciones de Alembic, carga `seed/pilot_dataset.sql` y verifica conteos y sumas contra el manifiesto. Los conductores quedan sin credencial de despacho: se genera desde el panel (Conductores → Generar QR). Se niega a usar `flota_db` como destino. |

```bash
python scripts/seed_demo.py                # crea o recrea la base 'flota_seed'
python scripts/seed_demo.py --db otra_base
```

Para apuntar un servicio a la base sembrada sin tocar la viva:

```bash
docker compose exec -e POSTGRES_DB=flota_seed fleet-core-service <comando>
```

## Modelo de costos

| Script | Qué hace |
|---|---|
| `seed_costos_ejemplo.py` | Carga costos fijos por vehículo y costos de personal por conductor **ilustrativos** (sus notas empiezan por `EJEMPLO`; la regla de cálculo está en la cabecera del script). La base piloto no los trae. Es idempotente y solo toca filas `EJEMPLO`. Por defecto escribe en `flota_seed`; para la base viva exige `--viva`; `--project flota_verif` apunta a la pila de verificación; `--quitar` los borra. **Sobre `flota_verif`, córralo *después* de las pruebas de integración** (`tests/test_costos_smoke.py` calcula el devengo esperado para su propio vehículo/conductor de prueba y no descuenta costos EJEMPLO ya presentes; con ellos cargados, esas 4 pruebas fallan por datos, no por un defecto real — bórrelos con `--quitar` antes de repetir la suite). |
| `check_iva_rates.py` | Compara las tarifas de IVA de `iva_config.json` (backend) con las de `frontend/src/utils/tax.ts`. Con `--estricto` falla también mientras no las verifique un contador. |
| `gen_doc_modelo_costos.py` | Regenera `12_RESULTADOS_OBTENIDOS/modelo_de_costos_indicadores.md` (tabla indicador → fórmula → fuente → código) desde `cost_model.py`. Con `--check` falla si el documento no está al día. |

```bash
python scripts/seed_costos_ejemplo.py                      # sobre flota_seed
python scripts/seed_costos_ejemplo.py --db flota_db --viva # base viva
python scripts/check_iva_rates.py
python scripts/gen_doc_modelo_costos.py --check
```

## Prueba de carga

`scripts/loadtest/` tiene la prueba de carga del tablero con k6 (RNF-01: consultas en menos de 2 s con
10 usuarios concurrentes) y el generador de su informe. Se corre contra la pila de verificación; ver
`scripts/loadtest/README.md`. Resultados: `12_RESULTADOS_OBTENIDOS/prueba_de_carga_tablero.md`.

## Aislamiento de roles en la base de datos

Cada servicio que usa PostgreSQL se conecta con su propio rol, dueño exclusivo de su esquema y sin
ningún permiso sobre el del otro (`infra/postgres/roles.sql`); el superusuario de la instancia
(`POSTGRES_USER`) ya no lo usa ningún servicio. En una base **nueva** esto lo aplica solo
`infra/postgres/init.sh` la primera vez que arranca el volumen (`docker-entrypoint-initdb.d`). En una
base que **ya existía** antes de este cambio (por ejemplo, la base viva), hay que aplicarlo a mano una
vez:

```bash
python scripts/apply_db_roles.py --db flota_db --viva --auth-password ... --fleet-password ...
docker compose up -d --force-recreate postgres auth-service fleet-core-service
docker compose restart gateway
```

Es idempotente (se puede volver a correr sin daño) y también sirve para retroceder una base que se
sembró antes de esta separación (`seed_demo.py`, `bench_queries.py` ya crean el esquema con el dueño
correcto en una base nueva).

## Benchmark de consultas

`bench_queries.py` mide las consultas de fleet-core-service a 10³, 10⁵ y 10⁶ viajes sintéticos, sin y
con los índices de la migración `f4a8c2d6e9b1` (RNF-01/RNF-05). Corre contra una base desechable
(`flota_bench`) dentro de la pila indicada; nunca toca la base viva ni la de trabajo.

```bash
python scripts/bench_queries.py --project flota_verif                     # 10^3, 10^5 y 10^6 viajes
python scripts/bench_queries.py --project flota_verif --scales 1000 100000
python scripts/bench_queries.py --informe                                 # solo regenera el informe
```

Resultados: `12_RESULTADOS_OBTENIDOS/benchmark_consultas.md` (regenerado desde
`12_RESULTADOS_OBTENIDOS/benchmark/escala_*.json`).

## Código compartido entre servicios

Los tres microservicios son procesos independientes y no comparten un paquete de Python en tiempo de
ejecución; donde la lógica SÍ es la misma a propósito (hoy, solo `app/core/config_guard.py`, RNF-02) se
copia adrede, y `check_shared_code.py` detecta si una copia se editó sin llevar el cambio a las otras
(lo corre `.github/workflows/ci.yml`):

```bash
python scripts/check_shared_code.py
```

## Cobertura de las pruebas unitarias

`pytest.ini` y `.coveragerc` (uno por servicio) miden la cobertura de las pruebas **unitarias**
(`pytest -m "not smoke"`, sin el stack levantado); las de integración (`test_*_smoke.py`) se marcan
`smoke` automáticamente por su nombre de archivo (`tests/conftest.py`) y quedan fuera, porque corren la
aplicación en otro proceso.

```bash
for s in auth-service fleet-core-service reporting-service; do
  docker run --rm -v "$PWD/services/$s:/app" -v "$PWD/../12_RESULTADOS_OBTENIDOS/coverage:/out" \
    -w /app python:3.12-slim sh -c \
    "pip install -q -r requirements.txt -r requirements-test.txt httpx==0.27.2 && \
     python -m pytest tests -m 'not smoke' -q --cov=app --cov-report=term-missing --cov-report=xml:/out/coverage_$s.xml"
done
python scripts/gen_coverage_report.py      # 12_RESULTADOS_OBTENIDOS/cobertura_pruebas.md
```

## HTTPS y despliegue local de verificación

`docker-compose.prod.yml` verifica en este mismo equipo, con las mismas imágenes multietapa (sin
privilegios de administrador, con `HEALTHCHECK`) que se usarían en un despliegue real, que RNF-02
(HTTPS) y el resto de la infraestructura funcionan de verdad. Ver la cabecera de ese archivo para el
uso completo; en resumen:

```bash
python scripts/gen_dev_tls_cert.py                 # certificado TLS autofirmado (o instale mkcert)
cp .env.prod.example .env.prod                      # complete secretos REALES; .env.prod no se versiona
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Cuándo reexportar

Solo si cambia a propósito la base piloto (y por tanto las cifras del documento). Después
de reexportar, actualice el documento y la matriz de trazabilidad
(`07_MATRICES_DE_ANALISIS/matriz_trazabilidad.xlsx`, filas N-01 y N-07).

## Evidencias para el documento y el README

| Script | Qué hace |
|---|---|
| `gen_er_diagram.py` | Genera el modelo entidad-relación (Mermaid) y el diccionario de datos desde el esquema en ejecución; con `--check` falla si el diagrama quedó desactualizado. |
| `gen_informe_pruebas.py` | Resume los JUnit XML de las tres suites (unitarias e integración) en el informe de pruebas que cita el documento. |
| `gen_cifras_avance2.py` | Reúne en un JSON las cifras que citó el documento del Avance 2 (pruebas, AHP, cobertura, carga). Se conserva como registro de esa entrega. |
| `enlace_despacho_demo.py` | Emite una credencial QR nueva para un conductor ficticio de la base de prueba y escribe el enlace del portal de despacho, para mostrarlo en el navegador con la vista de celular. |
| `capturas_readme.py` | Toma las capturas de `docs/capturas/` y graba el recorrido de `docs/video/` con Playwright, con la pila local corriendo. |

## Pila de verificación aislada

Las pruebas de integración (`services/*/tests/test_*_smoke.py`) **escriben datos**: crean y
cancelan viajes, rotan la credencial de un conductor, activan y desactivan un usuario
operador de prueba. Para no ensuciar la base de trabajo se corren contra una pila
paralela con base propia y otros puertos (gateway en `:18080`, frontend en `:15173`):

```bash
docker compose build
python scripts/make_verif_nginx.py         # gateway de verificación con límites de tasa relajados
docker compose -p flota_verif -f docker-compose.yml -f infra/docker-compose.verif.yml up -d
docker compose -p flota_verif exec -T postgres psql -U flota -d flota_db -v ON_ERROR_STOP=1 -q < scripts/seed/pilot_dataset.sql

# pruebas de un servicio (unitarias + integración) dentro de un contenedor desechable; en Git Bash
# de Windows anteponga MSYS_NO_PATHCONV=1. host.docker.internal es el anfitrión visto desde el contenedor.
docker run --rm -e FLOTA_BASE_URL=http://host.docker.internal:18080/api \
  -v "$PWD/services/fleet-core-service:/app" -w /app python:3.12-slim sh -c \
  "pip install -q -r requirements.txt -r requirements-test.txt && python -m pytest tests -q"

docker compose -p flota_verif down -v      # elimina la pila y su volumen
```

`RUN_RATE_LIMIT_TESTS=1` activa la prueba que agota el cupo de peticiones del gateway
(queda bloqueado ~1 minuto, por eso no corre por defecto). Solo tiene sentido contra un gateway
con los límites reales (`infra/nginx/nginx.conf`), no contra el de verificación, que los relaja.
