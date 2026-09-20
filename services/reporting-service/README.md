# reporting-service

Panel de indicadores (dashboard), priorización de mantenimiento por AHP y
reportes exportables (RF-15 a RF-20). No tiene base de datos propia: agrega
datos consultando a `fleet-core-service` por HTTP (endpoints `/analytics/*`,
ya agregados en SQL), reenviando el mismo token del usuario que hizo la
petición original — respeta el límite de esquema entre servicios en lugar
de leer directamente las tablas de `fleet`.

## Estructura

```
app/
├── main.py            # instancia FastAPI + /health
├── core/
│   ├── security.py     # verificación de JWT (misma clave que los otros servicios)
│   ├── deps.py          # get_current_user (expone el token para reenviarlo)
│   └── fleet_client.py   # cliente HTTP hacia fleet-core-service
└── dashboards/
    ├── schemas.py        # tipos de respuesta de todos los endpoints
    ├── ahp.py              # RF-20: Analytic Hierarchy Process (Saaty, 1980)
    ├── service.py            # agregación en memoria de lo que ya llega sumado por SQL
    ├── export.py              # RF-17: genera .xlsx (openpyxl) y .pdf (reportlab)
    └── router.py               # todos los GET /dashboard/* y /reports/*
```

## Endpoints

| Método | Ruta | RF |
|---|---|---|
| GET | `/dashboard/summary?vehicle_id=&date_from=&date_to=&category=` | RF-15, RF-16 |
| GET | `/dashboard/trend?period=week\|month\|year&...` | RF-16 (tendencia en el tiempo) |
| GET | `/dashboard/records?...` | insumo de histograma/dispersión del tablero |
| GET | `/dashboard/drivers?...` | costo y eficiencia por conductor |
| GET | `/dashboard/routes?...` | costo y distancia por ruta |
| GET | `/dashboard/maintenance-status?vehicle_id=` | alertas por urgencia + mezcla preventivo/correctivo |
| GET | `/dashboard/maintenance-priority?vehicle_id=` | **RF-20**: ranking AHP (seguridad, urgencia, costo) |
| GET | `/reports/maintenance?...` | RF-17: detalle de mantenimientos del período |
| GET | `/reports/costs.xlsx` \| `/reports/costs.pdf` | RF-17: exportación |

`dashboard/summary` devuelve, por vehículo: costo total, desglose por tipo
de gasto, ingreso y margen (cuando hay datos de flete registrados),
consumo de combustible (L/100km) y % de utilización del período —
calculado a partir de unas pocas llamadas a `/analytics/*` de
`fleet-core-service`, no una por cada viaje o gasto.

`dashboard/maintenance-priority` (RF-20) es el módulo AHP: combina
seguridad (criticidad del tipo de mantenimiento), urgencia (kilometraje
restante) y costo estimado con una matriz de comparación pareada validada
por su ratio de consistencia (CR = 0.033, muy por debajo del umbral de
aceptación 0.10). Ver `app/dashboards/ahp.py` para la matriz completa y su
justificación.

Si `fleet-core-service` no responde o rechaza el token, este servicio
devuelve 503 o el mismo código de error recibido — no falla en silencio.

## Pruebas

```bash
docker compose exec reporting-service sh -c "pip install -q -r requirements-test.txt && pytest -q"
```

Incluye pruebas unitarias puras del módulo AHP (pesos suman 1, matriz
consistente, seguridad > urgencia > costo, casos límite) además de las
pruebas de integración HTTP. Cobertura real medida con `coverage.py`: 75%
(78% combinado con los otros dos servicios).
