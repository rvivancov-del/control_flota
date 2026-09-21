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
    ├── ahp.py              # RF-19/RF-20: Analytic Hierarchy Process (Saaty, 1980)
    ├── ahp_config.json      # juicios del AHP con su estado y procedencia (matriz, criticidad, costos, curva de urgencia)
    ├── ahp_analysis.py       # análisis de sensibilidad del ranking (tau de Kendall, perturbación de pesos)
    ├── alert_policy.py        # RF-13: clasifica vencido / próximo / normal con el umbral de la configuración
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
| GET | `/dashboard/vehicle-attention?urgency_over_cost=&limit=&...` | **RF-19**: ranking de atención por vehículo (AHP de 2 criterios: urgencia y costo) |
| GET | `/reports/maintenance?...` | RF-17: detalle de mantenimientos del período |
| GET | `/reports/costs.xlsx` \| `/reports/costs.pdf` | RF-17: exportación |

`dashboard/summary` devuelve, por vehículo: costo total, desglose por tipo
de gasto, ingreso y margen (cuando hay datos de flete registrados),
consumo de combustible (L/100km) y % de utilización del período —
calculado a partir de unas pocas llamadas a `/analytics/*` de
`fleet-core-service`, no una por cada viaje o gasto.

`dashboard/maintenance-priority` (RF-20) es el módulo AHP: combina
seguridad (criticidad del tipo de mantenimiento), urgencia (kilometraje
restante) y costo estimado con los pesos que salen de una matriz de
comparación pareada y de su razón de consistencia (CR < 0.10). Los juicios
NO están escritos en el código: viven en `app/dashboards/ahp_config.json`
(o en la ruta de `AHP_CONFIG_PATH`), que declara su `estado` y su
`procedencia`; la respuesta del endpoint los repite en `config`. Hoy el estado
es `provisional_desarrollador` (valores del autor, sin panel de expertos); se
reemplaza con la agregación de `07_MATRICES_DE_ANALISIS/ahp_juicios_expertos.xlsx`.
Un archivo inválido o con CR >= 0.10 detiene el arranque.

`dashboard/vehicle-attention` (RF-19) usa el mismo motor con dos criterios:
la razón de Saaty `urgency_over_cost` (1/9 a 9) da los pesos `a/(a+1)` y
`1/(a+1)`, y la urgencia de cada vehículo es la peor de sus mantenimientos
pendientes con la misma curva de urgencia de RF-20. Una matriz 2x2 es
consistente por construcción (CR = 0), así que no aporta verificación real.

`app/dashboards/ahp_analysis.py` mide la sensibilidad del ranking a cambios de
+-10/20/30 % en cada peso. Informe con la configuración vigente:
`python -m app.dashboards.ahp_analysis`.

Si `fleet-core-service` no responde o rechaza el token, este servicio
devuelve 503 o el mismo código de error recibido — no falla en silencio.

## Pruebas

Las pruebas unitarias del AHP no necesitan el stack levantado (las de
integración `test_reporting_smoke.py` sí). Desde este directorio:

```bash
docker run --rm -v "$PWD:/work" -w /work python:3.12-slim sh -c   "pip install -q -r requirements.txt -r requirements-test.txt && python -m pytest -q    tests/test_ahp.py tests/test_ahp_config.py tests/test_ahp_sensitivity.py tests/test_vehicle_attention.py"
```

Cubren: pesos y CR contra un cálculo independiente, regresión de la curva de
urgencia, validación estricta de `ahp_config.json`, sensibilidad del ranking
(primer lugar y top-3 estables hasta +-30 %, tau >= 0.90) y el ranking de RF-19.

La cobertura de pruebas de este servicio no tiene una cifra vigente: se mide
con `coverage.py` en la Fase 5 del plan de coherencia.
