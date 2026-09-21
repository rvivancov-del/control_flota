# fleet-core-service

Núcleo de la flota: vehículos, conductores, viajes, gastos operativos,
mantenimiento, agregación para reportería y despacho por código QR
(RF-04 a RF-14, RF-18).

## Estructura

```
app/
├── main.py         # instancia FastAPI + /health
├── core/           # configuración, conexión a base de datos, verificación de JWT
├── models/         # modelos SQLAlchemy compartidos del esquema "fleet"
├── vehicles/        # RF-04: alta, edición y baja de vehículos
├── drivers/          # RF-05: alta, edición de conductores + token de QR (RF-18)
├── trips/            # RF-06, RF-07, RF-14: viajes, kilometraje, consultas
├── expenses/         # RF-08, RF-09, RF-10: combustible, peajes, alimentación
├── maintenance/       # RF-11, RF-12, RF-13: tipos de mantenimiento, alertas por km y su política (policy.py + maintenance_policy.json)
├── despacho/           # RF-18: portal del conductor -- sin sesión, autenticado por token de QR
└── analytics/           # agregación SQL (SUM/GROUP BY) que consume reporting-service
```

Cada submódulo funcional tiene su propia carpeta (`schemas.py` + `router.py`)
para mantener el servicio organizado por dominio, aunque todos comparten el
mismo proceso y la misma base de datos (esquema `fleet`).

## Autenticación

Este servicio no emite tokens ni guarda contraseñas — verifica de forma
independiente los JWT que emitió `auth-service`, usando el mismo
`JWT_SECRET_KEY` (HS256, clave simétrica compartida). Todos los endpoints
requieren `Authorization: Bearer <token>`.

## Endpoints

| Método | Ruta | Rol | RF |
|---|---|---|---|
| POST/GET/PATCH | `/vehicles`, `/vehicles/{id}` | autenticado | RF-04 |
| POST/GET/PATCH | `/drivers`, `/drivers/{id}` | autenticado | RF-05 |
| POST | `/drivers/{id}/regenerate-qr` | autenticado | RF-18 (código QR perdido/robado) |
| POST/GET | `/trips`, `/trips/{id}` | autenticado | RF-06, RF-14 |
| PATCH | `/trips/{id}/start` \| `/cancel` \| `/close` \| `/revenue` | autenticado | RF-06, RF-07 (estados, Lámina D-05) |
| POST/GET | `/trips/{id}/expenses` | autenticado | RF-08, RF-09, RF-10 |
| POST/GET | `/vehicles/{id}/maintenance` | autenticado | RF-11, RF-12 |
| PATCH | `/maintenance/{id}/complete` \| `/cost` | autenticado | RF-11 |
| GET | `/maintenance/alerts` | autenticado | RF-13: pendientes vencidos o próximos, con `km_remaining` y `urgency` |
| GET | `/maintenance/policy` | autenticado | RF-13: umbral 'próximo' vigente, su estado y su procedencia |
| GET | `/despacho/{driver_id}?token=` | **público**, token de QR | RF-18 |
| POST | `/despacho/{driver_id}?token=` | **público**, token de QR | RF-18 |
| GET | `/analytics/expenses` \| `/trips` \| `/routes` \| `/maintenance` | autenticado (uso interno de reporting-service) | soporte de RF-15 a RF-20 |

`PATCH /trips/{id}/close` es el endpoint que implementa las Láminas D-03 y
D-06: además de cerrar el viaje, actualiza `vehicles.current_mileage_km` y
devuelve en la misma respuesta los mantenimientos que quedaron vencidos por
kilometraje — no hace falta una segunda llamada para saberlo.

`/despacho/*` es la única ruta de todo el sistema sin `Authorization:
Bearer` — el conductor se autentica con el token opaco de su código QR
(`Driver.qr_token`), comparado en el propio endpoint. Ver
`app/despacho/router.py`.

`/analytics/*` existe para que `reporting-service` no tenga que traer cada
viaje/gasto por HTTP y sumarlos en Python: la base de datos ya sabe sumar
(`SUM`/`GROUP BY`), así que un año de historia son unas pocas consultas SQL,
no miles de peticiones.

## Pruebas

```bash
docker compose exec fleet-core-service sh -c "pip install -q -r requirements-test.txt && pytest -q"
```

Cobertura real medida con `coverage.py`: 82%.

## Política de alertas de mantenimiento (RF-13)

`app/maintenance/policy.py` es el ÚNICO lugar que decide si un mantenimiento
pendiente está `vencido` (km restantes <= 0), `proximo` (faltan `proximo_km` o
menos) o `normal`. El historial por vehículo, `/maintenance/alerts` y el cierre
de viaje devuelven `km_remaining` y `urgency` ya calculados; reporting-service y
el frontend los consumen y **no aplican un umbral propio** (el frontend lee el
umbral de `/maintenance/policy`).

El umbral vive en `app/maintenance/maintenance_policy.json` (o en la ruta de
`MAINTENANCE_POLICY_PATH`), que declara su `estado` y su `procedencia`; admite
excepciones por tipo en `proximo_km_por_tipo`. Hoy el estado es
`provisional_desarrollador` (1500 km, sin respaldo de expertos) y se reemplaza con
la mediana de la pregunta 6.1 del cuestionario de expertos. Un archivo inválido
detiene el arranque. No hay notificaciones por SMS o WhatsApp (fuera de alcance):
la alerta es visible en la aplicación.

Pruebas unitarias (sin base de datos ni stack):

```bash
docker run --rm -v "$PWD:/work" -w /work python:3.12-slim sh -c   "pip install -q -r requirements.txt -r requirements-test.txt && python -m pytest -q tests/test_maintenance_policy.py"
```
