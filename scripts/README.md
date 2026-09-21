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

## Cuándo reexportar

Solo si cambia a propósito la base piloto (y por tanto las cifras del documento). Después
de reexportar, actualice el documento y la matriz de trazabilidad
(`07_MATRICES_DE_ANALISIS/matriz_trazabilidad.xlsx`, filas N-01 y N-07).

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
