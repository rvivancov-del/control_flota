# scripts/

Utilidades de reproducibilidad. Se ejecutan **desde la raíz del repositorio** con
`docker compose up` corriendo. Solo usan la biblioteca estándar de Python.

## Base piloto reproducible

Las cifras del documento de tesis (12 vehículos, 13 conductores, 640 viajes, 1.330
gastos y 96 mantenimientos) salen de la base piloto de `fleet-core-service`. Los datos
son ficticios (placas, licencias y teléfonos de ejemplo).

| Script | Qué hace |
|---|---|
| `export_pilot_dataset.py` | Lee la base viva (`flota_db`, solo lectura) y escribe `seed/pilot_dataset.sql` y `seed/pilot_dataset.manifest.json` (conteos, sumas y hash SHA-256). El `qr_token` de los conductores **no** se exporta: es una credencial. |
| `seed_demo.py` | Recrea una base de demostración (por defecto `flota_seed`), crea el esquema `fleet`, aplica las migraciones de Alembic, carga `seed/pilot_dataset.sql`, genera `qr_token` nuevos y verifica conteos y sumas contra el manifiesto. Se niega a usar `flota_db` como destino. |

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
