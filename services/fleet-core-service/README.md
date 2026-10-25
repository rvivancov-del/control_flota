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
├── drivers/          # RF-05: alta, edición de conductores + credencial de QR (RF-18)
├── trips/            # RF-06, RF-07, RF-14: viajes, kilometraje, consultas
├── expenses/         # RF-08, RF-09, RF-10: combustible, peajes, alimentación
├── maintenance/       # RF-11, RF-12, RF-13: tipos de mantenimiento, alertas por km y su política (policy.py + maintenance_policy.json)
├── despacho/           # RF-18: portal del conductor -- sin sesión, autenticado por credencial personal (qr_token.py)
└── analytics/           # agregación SQL (SUM/GROUP BY) que consume reporting-service
```

Cada submódulo funcional tiene su propia carpeta (`schemas.py` + `router.py`)
para mantener el servicio organizado por dominio, aunque todos comparten el
mismo proceso y la misma base de datos (esquema `fleet`).

## Autenticación

Este servicio no emite tokens ni guarda contraseñas — verifica de forma
independiente los JWT que emitió `auth-service`, usando el mismo
`JWT_SECRET_KEY` (HS256, clave simétrica compartida). Todos los endpoints
requieren `Authorization: Bearer <token>`, salvo `/despacho/*` (ver más abajo).

### Permisos por rol (RF-03)

El rol viaja en el JWT (`admin` u `operador`) y se exige con `require_role`
(`app/core/deps.py`). Un rol desconocido no accede a nada: la lista de roles
operativos es explícita. `operador` opera el día a día; `admin` además
administra el catálogo y la credencial de despacho.

| Operación | admin | operador |
|---|:-:|:-:|
| Consultar vehículos, conductores, viajes, gastos, mantenimientos y analítica | sí | sí |
| Crear/editar viajes (iniciar, cancelar, cerrar, ingreso) | sí | sí |
| Registrar gastos y mantenimientos (crear, completar, costo) | sí | sí |
| Crear/editar vehículos y conductores | sí | no (403) |
| Emitir, rotar o revocar el QR de un conductor | sí | no (403) |

Consecuencia declarada: como este servicio no consulta a auth-service, un cambio
de rol o una baja de usuario se refleja cuando expira el JWT vigente (60 min).

## Endpoints

| Método | Ruta | Rol | RF |
|---|---|---|---|
| GET | `/vehicles`, `/vehicles/{id}` | admin, operador | RF-04 |
| POST/PATCH | `/vehicles`, `/vehicles/{id}` | **admin** | RF-04 |
| GET | `/drivers`, `/drivers/{id}` | admin, operador | RF-05 (sin token: solo `has_qr`, vigencia y último uso) |
| POST/PATCH | `/drivers`, `/drivers/{id}` | **admin** | RF-05 (el alta devuelve el token del QR, una sola vez) |
| POST | `/drivers/{id}/regenerate-qr` | **admin** | RF-18 rotación (QR perdido/robado); devuelve el token nuevo, una sola vez |
| POST | `/drivers/{id}/revoke-qr` | **admin** | RF-18 revocación sin emitir otro |
| GET | `/drivers/license-types` | admin, operador | RF-05: tipos de licencia vigentes (ANT) que acepta el sistema |
| POST | `/drivers/{id}/anonymize` | **admin** | RNF-11: suprime los datos personales del conductor (irreversible) |
| POST/GET | `/trips`, `/trips/{id}` | admin, operador | RF-06; RF-14: `GET /trips` filtra por `vehicle_id`, `driver_id`, `status_filter`, `date_from`, `date_to` |
| PATCH | `/trips/{id}/start` \| `/cancel` \| `/close` \| `/revenue` | admin, operador | RF-06, RF-07 (estados, Lámina D-05) |
| POST/GET | `/trips/{id}/expenses` | admin, operador | RF-08, RF-09 (el peaje exige `location`), RF-10 |
| GET | `/expenses` | admin, operador | RF-14: gastos de todos los viajes, filtrados por `vehicle_id`, `driver_id`, `type`, `date_from`, `date_to` (máx. `limit`=1000 por defecto, 5000) |
| POST/GET | `/vehicles/{id}/maintenance` | admin, operador | RF-11, RF-12 |
| PATCH | `/maintenance/{id}/complete` \| `/cost` | admin, operador | RF-11 |
| GET | `/maintenance/alerts` | admin, operador | RF-13: pendientes vencidos o próximos, con `km_remaining` y `urgency` |
| GET | `/maintenance/policy` | admin, operador | RF-13: umbral 'próximo' vigente, su estado y su procedencia |
| GET | `/despacho/{driver_id}` | **público**, cabecera `X-Despacho-Token` | RF-18 |
| POST | `/despacho/{driver_id}` | **público**, cabecera `X-Despacho-Token` | RF-18 |
| GET | `/analytics/expenses` \| `/trips` \| `/routes` \| `/maintenance` | admin, operador (uso interno de reporting-service) | soporte de RF-15 a RF-20 |

`PATCH /trips/{id}/close` es el endpoint que implementa las Láminas D-03 y
D-06: además de cerrar el viaje, actualiza `vehicles.current_mileage_km` y
devuelve en la misma respuesta los mantenimientos que quedaron vencidos por
kilometraje — no hace falta una segunda llamada para saberlo.

`/despacho/*` es la única ruta de todo el sistema sin `Authorization:
Bearer` — el conductor se autentica con la credencial personal de su código QR.
Un QR fijo en la cabina se escanea en cada viaje, así que la credencial no es
de un solo uso; es **personal, revocable y con vigencia** (RF-18):

- 192 bits aleatorios; en la base solo se guarda su SHA-256 (`drivers.qr_token_hash`). El
  token en claro se devuelve una única vez, al emitirlo o rotarlo, y no se puede volver a consultar.
- Comparación en tiempo constante y respuesta uniforme `401` si el conductor no existe, el
  token es falso, venció o fue revocado.
- Vigencia de `QR_TOKEN_TTL_DAYS` días (180 por defecto; el servicio no arranca si el valor es inválido);
  se guardan emisión y último uso.
- Viaja en la cabecera `X-Despacho-Token`, no en la URL de la API, para que no quede en los registros
  de acceso del gateway; el gateway limita la tasa de peticiones a `/despacho/`.

Ver `app/despacho/qr_token.py` y `app/despacho/router.py`.

`/analytics/*` existe para que `reporting-service` no tenga que traer cada
viaje/gasto por HTTP y sumarlos en Python: la base de datos ya sabe sumar
(`SUM`/`GROUP BY`), así que un año de historia son unas pocas consultas SQL,
no miles de peticiones.

## Validaciones de dominio y datos personales

- **Licencia (RF-05):** solo se aceptan los tipos vigentes de la ANT (A, A1, B, C, C1, D, E, F, G; `app/drivers/licenses.py`). 'Tipo E' se normaliza a 'E' y los tipos históricos D1/E1 a D/E (Resolución 028-DE-ANT-2021). Los estados de vehículos y conductores y del filtro de viajes también se validan, y la base los respalda con restricciones CHECK.
- **Peaje (RF-09):** un peaje nuevo debe informar su ubicación (`location`); los 405 peajes históricos de la base piloto no la tienen.
- **Rectificación y supresión (RNF-11, LOPDP):** el admin puede corregir todos los datos de un conductor, incluida la licencia, y suprimirlos con `POST /drivers/{id}/anonymize`: se borran nombre, licencia, teléfono y credencial de despacho, y el conductor queda inactivo. Los viajes y gastos se conservan como historial contable sin identificar a la persona. Es irreversible y se rechaza si el conductor tiene viajes planificados o en curso. Los conductores (con licencia y teléfono) son visibles para los dos roles operativos, porque el operador los necesita para registrar viajes.
- **Odómetro (RF-07):** cerrar un viaje nunca hace retroceder el kilometraje del vehículo.

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
excepciones por tipo en `proximo_km_por_tipo`. El umbral vigente
es de 1000 km: la mediana de la pregunta 6.1 del cuestionario de expertos
(estado `expertos_n=3`). Un archivo inválido
detiene el arranque. No hay notificaciones por SMS o WhatsApp (fuera de alcance):
la alerta es visible en la aplicación.

Pruebas unitarias (sin base de datos ni stack):

```bash
docker run --rm -v "$PWD:/work" -w /work python:3.12-slim sh -c   "pip install -q -r requirements.txt -r requirements-test.txt && python -m pytest -q tests/test_maintenance_policy.py"
```
