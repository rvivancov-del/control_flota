# FlotaControl — Sistema de Control de Flota de Carga Pesada

Sistema web para el control de costos operativos y mantenimiento de vehículos
de carga pesada, desarrollado como trabajo de titulación (UNEMI, Ingeniería
en Sistemas — certificación EUR-ACE).

**Estado real, verificado (no aspiracional):** los 20 requerimientos
funcionales declarados (RF-01 a RF-20) están implementados, probados y
funcionando de punta a punta — backend, frontend y base de datos — sobre los
tres microservicios descritos abajo. Cobertura de pruebas medida con
`coverage.py` sobre los tres servicios: 71–82% por servicio, 78% combinado
(suite de 28 pruebas), por encima de la meta declarada en RNF-07 (≥60%).

## Qué hace

- Registra vehículos, conductores, viajes, gastos (combustible, peajes,
  alimentación) y mantenimiento (preventivo, correctivo, programado por
  kilometraje) de una flota de camiones.
- Calcula costo total, costo por kilómetro, margen (ingreso − costo),
  consumo de combustible y utilización de la flota, con gráficas de
  tendencia, distribución y composición del gasto.
- Alerta automáticamente cuándo un mantenimiento vence por kilometraje, y
  prioriza qué vehículo atender primero combinando **seguridad, urgencia y
  costo** con el método Analytic Hierarchy Process (Saaty, 1980) — no un
  solo criterio arbitrario.
- Permite que un conductor registre su propio viaje **desde su celular,
  escaneando un código QR pegado en la cabina**, sin usuario ni contraseña
  — pensado para que funcione en el punto de carga/descarga real, no solo
  en la oficina.
- Exporta reportes de costos y mantenimientos a Excel y PDF.

## Arquitectura

```
                 Navegador (React + TypeScript)
                            │  HTTPS / JSON
                            ▼
              Gateway / Reverse Proxy (nginx)
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  auth-service       fleet-core-service    reporting-service
  (JWT, usuarios,     (vehículos, viajes,    (dashboard, KPIs,
   roles)              gastos, manten.,       reportes — sin
                        despacho por QR)       base de datos propia)
        │                   │                        │
        └─────────┬─────────┘                        │
                   ▼                                  │
             PostgreSQL 16                 llama a fleet-core-service
      (esquemas auth, fleet —                  por HTTP con el mismo
       uno por servicio dueño)                    token del usuario
```

Tres microservicios independientes (FastAPI + SQLAlchemy + Alembic), cada
uno dueño exclusivo de su propio esquema de base de datos — sin claves
foráneas de base de datos entre esquemas de distintos servicios (por
ejemplo, `trips.created_by` referencia a `auth.users.id` solo a nivel de
aplicación, nunca como FK real). `reporting-service` no tiene tablas
propias: agrega sus indicadores llamando a `fleet-core-service` por HTTP.

Diagramas completos (arquitectura, modelo entidad-relación, UML de
comportamiento) en
[`08_DIAGRAMAS_MODELOS_Y_DISENO/`](../08_DIAGRAMAS_MODELOS_Y_DISENO/diagramas_individuales/00_indice.html)
de la carpeta de tesis, y el SQL real de la base de datos en
[`06_BASES_DE_DATOS_UTILIZADAS/flota_control_schema.sql`](../06_BASES_DE_DATOS_UTILIZADAS/flota_control_schema.sql).

## Estructura

```
sistema-control-flota/
├── docker-compose.yml       # orquesta todo el entorno de desarrollo local
├── infra/
│   ├── nginx/                # gateway / reverse proxy
│   └── postgres/init.sql     # crea los esquemas auth / fleet / reporting
├── services/
│   ├── auth-service/          # autenticación, usuarios y roles — ver su README
│   ├── fleet-core-service/     # vehículos, viajes, gastos, mantenimiento, despacho QR — ver su README
│   └── reporting-service/      # dashboard, AHP, reportes — ver su README
└── frontend/                  # SPA React + TypeScript + Vite — ver su README
```

Cada microservicio tiene su propia carpeta `app/`, `requirements.txt`,
`Dockerfile` y `.env.example`. El detalle de endpoints, módulos internos y
decisiones de diseño de cada uno está en el `README.md` de su propia
carpeta — este documento cubre solo la vista de conjunto.

## Cómo levantar el entorno local

1. `docker-compose.yml` lee directamente los `.env.example` de cada
   servicio (valores de prueba locales, sin secretos reales — por eso
   están versionados). Antes de un despliegue real, crea un `.env` propio
   por servicio y cambia la referencia `env_file`.
2. Desde esta carpeta:

   ```bash
   docker compose up --build
   ```

3. Servicios disponibles:
   - Frontend: http://localhost:5173
   - API (gateway): http://localhost:8080/api/auth/... · /api/fleet/... · /api/reports/...
   - PostgreSQL: localhost:5432
   - Usuario inicial: `admin` / `Admin1234` (creado por `auth-service/app/seed.py`
     en el primer arranque — cámbialo antes de cualquier despliegue real).

### Generar una migración nueva (al cambiar un modelo)

```bash
docker compose run --rm --no-deps -v "$(pwd)/services/<servicio>:/app" <servicio> \
  alembic revision --autogenerate -m "descripción del cambio"
```

Revisa siempre el archivo generado en `migrations/versions/` antes de
aplicarlo. `docker compose up --build` lo aplica automáticamente al iniciar
(`alembic upgrade head` corre antes de `uvicorn`, ver el `CMD` del Dockerfile).

### Correr las pruebas de un servicio

```bash
docker compose exec <servicio> sh -c "pip install -q -r requirements-test.txt && pytest -q"
```

## Solución de problemas

### "404 Not Found" en cualquier ruta `/api/...` después de reconstruir un servicio

El `gateway` (nginx) resuelve el nombre de cada servicio (`auth-service`,
`fleet-core-service`, `reporting-service`) **una sola vez**, al arrancar, y
cachea la IP interna de Docker que le corresponde en ese momento. Si luego
reconstruyes o recreas SOLO uno de esos servicios
(`docker compose up --build auth-service`, por ejemplo) sin tocar el
gateway, el contenedor nuevo recibe una IP distinta y nginx se queda
apuntando a la vieja. Solución:

```bash
docker compose restart gateway
```

Corre ese comando cada vez que reconstruyas un servicio por separado.
`docker compose up --build` (todos juntos) no tiene este problema porque el
gateway también se recrea en la misma pasada. Es una limitación exclusiva
del entorno local — no existe en producción (Cloud Run resuelve por
HTTPS/DNS público, no por IP interna de una red Docker).

### El conductor abre el QR y el navegador de su celular no conecta

El código QR codifica el `window.location.origin` de quien lo generó. Si el
panel de administración se abrió en `localhost`, el QR apunta a
`localhost:5173` — que en el celular del conductor se refiere al propio
celular, no a la computadora del administrador. Para pruebas en la misma
red local, abre el panel desde la IP de red de la computadora (por ejemplo
`http://192.168.1.37:5173`) antes de generar el QR. Para que funcione desde
cualquier lugar con internet (el caso de uso real), hace falta el
despliegue a la nube — ver `10_MANUALES_USUARIO_Y_TECNICO/manual_tecnico.docx`.

## Despliegue a producción (planeado, capa gratuita)

- **Cloud Run** (los tres microservicios) y **Firebase Hosting** (el
  frontend) son gratuitos de forma permanente dentro de sus cuotas
  ("Always Free" de Google Cloud).
- **Cloud SQL** no tiene capa gratuita permanente — la base de datos se
  aloja en una instancia Compute Engine `e2-micro` (sí incluida en la capa
  Always Free) con PostgreSQL propio, evaluando además el convenio
  institucional UNEMI–Google Cloud para créditos adicionales.
- Instructivo paso a paso en `10_MANUALES_USUARIO_Y_TECNICO/manual_tecnico.docx`.

## Alcance no incluido (fuera del alcance de este trabajo de titulación)

- Pruebas de resiliencia distribuida (fallos parciales de red entre
  servicios, condiciones de carrera bajo alta concurrencia).
- Notificaciones push/SMS/WhatsApp, ubicación GPS en tiempo real, control
  de vencimiento de documentos (SOAT, matrícula) y facturación electrónica
  — identificadas como posibles siguientes pasos, no como pendientes de
  esta fase.
