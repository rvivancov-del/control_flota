<div align="center">

<img src="docs/banner.svg" alt="FlotaControl — Cada kilómetro, bajo control" width="100%">

### Sistema web con arquitectura de microservicios para el control de costos operativos y mantenimiento de una flota de transporte de carga pesada, con priorización de mantenimiento mediante AHP

<p>
<img alt="Versión" src="https://img.shields.io/badge/versión-v1.1--avance2-1B3A5C?style=for-the-badge">
<img alt="Pruebas" src="https://img.shields.io/badge/pruebas-909%2F910%20aprobadas-2E8B57?style=for-the-badge">
<img alt="Cobertura" src="https://img.shields.io/badge/cobertura-80%25-2E8B57?style=for-the-badge">
<img alt="p95" src="https://img.shields.io/badge/tablero%20p95-1%2C19%20s-E87D1E?style=for-the-badge">
</p>
<p>
<img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
<img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
<img alt="React" src="https://img.shields.io/badge/React-TypeScript-61DAFB?logo=react&logoColor=black">
<img alt="Nginx" src="https://img.shields.io/badge/Nginx-gateway-009639?logo=nginx&logoColor=white">
<img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
</p>

**[Video](#-video-de-demostración)** · **[Capturas](#-capturas)** · **[Guía de uso](#-guía-de-uso)** · **[Instalación](#-instalación-y-guía-técnica)** · **[Arquitectura](#-arquitectura)** · **[Diseño UML](#-diseño-uml-y-modelo-de-datos)** · **[Pruebas](#-pruebas-y-calidad)**

</div>

---

<table>
<tr>
<td width="62%">

**FlotaControl** ayuda a una pequeña empresa de transporte de carga pesada a saber **cuánto le cuesta realmente cada camión y cada kilómetro**, a **decidir qué mantenimiento atender primero** y a que **el conductor registre su viaje desde el celular**, sin papeles dispersos ni una sola persona que lo sepa todo.

Trabajo de titulación de **Rosa Margarita Vivanco Vélez**, Ingeniería en Tecnologías de la Información, Universidad Estatal de Milagro (UNEMI).
Docentes: **M.Sc. Mirella Azucena Peralta Correa** y **M.Sc. María Gabriela Espinoza Bravo**.

> Todas las capturas, videos y datos de prueba son **ficticios**: no contienen datos personales reales.

</td>
<td width="38%" align="center">
<img src="docs/capturas/10_despacho_movil.png" alt="Portal del conductor en el celular" width="230">
<br><sub>Portal del conductor: despacho por QR</sub>
</td>
</tr>
</table>

## 🎬 Video de demostración

<div align="center">

<img src="docs/demo.gif" alt="Recorrido por el panel de FlotaControl" width="90%">

**▶️ [Ver el video completo del panel (MP4)](docs/video/demo_panel.mp4)** · **📱 [Ver el despacho desde el celular (MP4)](docs/video/demo_despacho_movil.mp4)**

</div>

## ✨ Qué hace

<table>
<tr>
<td width="33%" valign="top">

### 💰 Costo real
Convierte cada gasto del viaje en **costo por vehículo y por kilómetro**. Suma los costos fijos y de personal: **Ct = Cv + Cf**, en las ocho categorías del costo de un vehículo-km. Muestra los montos con y sin IVA.

</td>
<td width="33%" valign="top">

### 🔧 Mantenimiento priorizado
Envía **alertas por kilometraje** (vencido o próximo) y ordena los mantenimientos pendientes con el **método AHP**, que combina seguridad, urgencia y costo con pesos configurables.

</td>
<td width="33%" valign="top">

### 📱 Despacho por QR
El conductor escanea **su credencial QR personal**, que es revocable y vale 180 días, y registra la salida desde su celular, **sin usuario ni contraseña**. Si no hay señal, el registro se guarda y se reenvía después.

</td>
</tr>
<tr>
<td valign="top">

### 📊 Tablero
Muestra el gasto operativo, la proyección de cierre, el consumo en L/100 km, la utilización de la flota, la utilidad, la tendencia, la composición del gasto y los gastos atípicos.

</td>
<td valign="top">

### 🔐 Seguridad
Usa roles (Administrador y Operador), contraseñas con hash, JWT con vigencia, bloqueo tras intentos fallidos, límite de solicitudes y HTTPS en producción. Los datos se tratan según la LOPDP.

</td>
<td valign="top">

### 📤 Reportes
Exporta los costos y los mantenimientos por vehículo y período a **Excel y PDF**, listos para el área contable.

</td>
</tr>
</table>

## 📸 Capturas

| Inicio de sesión | Tablero de indicadores |
|:---:|:---:|
| <img src="docs/capturas/01_inicio_sesion.png" alt="Inicio de sesión"> | <img src="docs/capturas/02_tablero.png" alt="Tablero"> |
| **Estructura del costo: Ct = Cv + Cf en ocho categorías** | **Alertas y prioridad de atención** |
| <img src="docs/capturas/03_estructura_costos.png" alt="Estructura de costos"> | <img src="docs/capturas/04_alertas_y_prioridad.png" alt="Alertas y prioridad"> |
| **Ranking AHP de mantenimientos** | **Viajes** |
| <img src="docs/capturas/05_ranking_ahp.png" alt="Ranking AHP"> | <img src="docs/capturas/06_viajes.png" alt="Viajes"> |
| **Flota de vehículos** | **Costos fijos y de personal** |
| <img src="docs/capturas/07_vehiculos.png" alt="Vehículos"> | <img src="docs/capturas/08_costos_fijos.png" alt="Costos fijos"> |
| **Reportes (Excel y PDF)** | |
| <img src="docs/capturas/09_reportes.png" alt="Reportes"> | |

---

## 📘 Guía de uso

<details open>
<summary><b>1. Ingresar al sistema</b></summary>

1. Abre el navegador en `http://localhost:5173`, o en la dirección que indique quien administra el sistema.
2. Escribe tu usuario y contraseña, y pulsa **Ingresar**.
3. La sesión dura 60 minutos. Si se cierra sola, vuelve a ingresar.

| Rol | Qué puede hacer |
|---|---|
| **Administrador** | Todo, además de **Usuarios** (crear cuentas y asignar roles) y **Costos** (costos fijos y de personal) |
| **Operador** | Registrar viajes, gastos y mantenimientos, y consultar el tablero y los reportes |
| **Conductor** | No tiene cuenta: despacha su viaje con su **credencial QR** desde el celular |

No hay registro desde la pantalla de inicio: solo un administrador crea cuentas.
</details>

<details>
<summary><b>2. Leer el tablero</b></summary>

Es la primera pantalla. Elige **Semana, Mes o Año**, avanza o retrocede de período con las flechas y alterna **Con IVA / Sin IVA**.

| Indicador | Qué significa |
|---|---|
| Gasto operativo de la flota | Combustible, peajes, alimentación y mantenimiento del período, comparados con el período anterior |
| Proyección de cierre | En cuánto cerrará el período al ritmo actual (con un rango probable) |
| Costo total por kilómetro | Ct / km recorridos: el indicador clave del sector |
| Mantenimientos urgentes | Vehículos con mantenimiento vencido o próximo por kilometraje |
| Utilidad del período | Ingreso (fletes cobrados) menos el costo total |
| Consumo de combustible | Litros por cada 100 km, distinto del costo porque el precio del diésel cambia |
| Utilización de la flota | Porcentaje de días con al menos un viaje |

Más abajo están:
- la **estructura del costo** en ocho categorías;
- la **acción requerida**: mantenimientos por atender y prioridad de atención;
- la comparación entre mantenimiento preventivo y correctivo, y las gráficas de tendencia, composición y distribución.
</details>

<details>
<summary><b>3. Registrar la flota: vehículos y conductores</b></summary>

- **Vehículos → Nuevo vehículo:** placa, marca, modelo, año, matrícula y kilometraje actual. Con **Editar** se modifica un vehículo o se marca como inactivo.
- **Conductores → Nuevo conductor:** nombre, número y tipo de licencia (ANT), teléfono y vehículo asignado.
</details>

<details>
<summary><b>4. Viajes y gastos</b></summary>

1. **Viajes → Nuevo viaje:** vehículo, conductor, origen, destino, fecha de salida y kilometraje inicial.
2. El viaje pasa por los estados **planificado → en curso → completado**; también puede quedar **anulado**.
3. **Para cerrar el viaje**, indica:
   - el kilometraje final (los km recorridos se calculan solos);
   - la fecha de llegada;
   - opcionalmente, el **ingreso del flete**, que permite calcular la utilidad.
4. En el detalle del viaje, **Agregar gasto**:
   - **combustible**, con los litros;
   - **peaje**, con la ubicación;
   - **alimentación**.

   Cada gasto muestra su base imponible y su IVA.
</details>

<details>
<summary><b>5. Despacho por código QR (conductores)</b></summary>

1. **El administrador:**
   - va a **Conductores → Gestionar QR → Generar código**;
   - pulsa **Imprimir tarjeta** y la pega en la cabina.
   
   La credencial vale 180 días y se puede **revocar** o **renovar** en cualquier momento.
2. **El conductor:**
   - escanea el QR con la cámara del celular;
   - completa origen, destino y kilometraje de salida;
   - pulsa **Registrar e iniciar viaje**.
3. **Sin señal:** el viaje queda guardado en el teléfono y se envía con **Reintentar envío**.
</details>

<details>
<summary><b>6. Mantenimiento y prioridad</b></summary>

- **Mantenimiento → Nuevo mantenimiento:**
  - tipo: aceite, filtros, llantas, frenos, bocines u otro;
  - categoría: preventivo, correctivo o programado por km;
  - kilometraje programado.
- Las **alertas** aparecen arriba de la lista cuando un mantenimiento está vencido o próximo.
- **«Qué reparar primero»** ordena los pendientes con el AHP según seguridad, urgencia y costo. El primero de la lista es el que conviene atender primero.
- Con **Completar** se registran el kilometraje real, la fecha y el costo del mantenimiento hecho.
</details>

<details>
<summary><b>7. Costos fijos, reportes y usuarios (administrador)</b></summary>

- **Costos:**
  - por vehículo: depreciación, capital, seguro, impuestos y otros;
  - por conductor: sueldo y beneficios.

  Cada uno se registra como monto mensual o anual, con su vigencia; el sistema lo prorratea por días.
- **Reportes:** elige el vehículo, el período y el IVA, y pulsa **Excel** o **PDF**.
- **Usuarios:**
  - para crear una cuenta, pulsa **Nuevo usuario**; la contraseña necesita al menos 8 caracteres, con letras y números;
  - con **Editar** se cambia el rol o la contraseña, o se desactiva la cuenta.
</details>

---

## 🛠️ Instalación y guía técnica

### Requisitos
| Programa | Para qué |
|---|---|
| [Git](https://git-scm.com/downloads) | Clonar el repositorio |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Ejecutar todo: los 3 servicios, la base de datos, el gateway y el frontend |

No hace falta instalar Python, Node.js ni PostgreSQL: todo corre en contenedores.

### Puesta en marcha (5 minutos)
```bash
git clone https://github.com/rvivancov-del/control_flota.git
cd control_flota
docker compose up --build -d
docker compose ps        # los 6 contenedores deben estar «Up» o «healthy»
```

| Dirección | Qué es |
|---|---|
| http://localhost:5173 | La aplicación |
| http://localhost:8080/api | El gateway, puerta de entrada al backend |

**Usuario inicial (solo para el entorno local de prueba):** `admin` / `Admin1234`.
- Lo crea `services/auth-service/app/seed.py` en el primer arranque.
- Fuera del modo de desarrollo, el sistema exige una clave propia y pide cambiarla al primer ingreso.

**Datos de prueba:** la base de prueba ficticia (12 vehículos, 13 conductores y 640 viajes) está en `scripts/seed/pilot_dataset.sql`. Las instrucciones para cargarla están en [`scripts/README.md`](scripts/README.md).

### Comandos útiles
| Comando | Qué hace |
|---|---|
| `docker compose up --build -d` | Construye y levanta todo en segundo plano |
| `docker compose ps` | Muestra el estado de cada contenedor |
| `docker compose logs <servicio>` | Muestra los registros de un servicio (por ejemplo, `fleet-core-service`) |
| `docker compose restart gateway` | Arregla el error «No se pudo conectar con el servidor» si el gateway arrancó antes que los servicios |
| `docker compose down` | Detiene todo; los datos se conservan |
| `docker compose down -v` | Detiene todo y **borra** la base de datos local |
| `docker compose exec -T postgres pg_dump -U flota -d flota_db --clean --if-exists > respaldo.sql` | Respaldo de la base |
| `docker compose exec -T postgres psql -U flota -d flota_db < respaldo.sql` | Restaura un respaldo |
| `docker compose -f docker-compose.prod.yml up -d` | Producción local con HTTPS: imágenes multietapa, sin usuario root, secretos en `.env.prod`. Ver `.env.prod.example` |

### Solución de problemas
| Síntoma | Causa y solución |
|---|---|
| «No se pudo conectar con el servidor» al iniciar sesión | El gateway arrancó antes que los servicios: `docker compose restart gateway` |
| `docker` no se reconoce o *failed to connect to the docker API* | Docker Desktop no está abierto: ábrelo y espera a que diga *Engine running* |
| *port is already allocated* | Otro programa usa el puerto 5173 u 8080: ciérralo o cambia el puerto de la izquierda en `docker-compose.yml` (por ejemplo, `8090:80`) |
| Un contenedor queda en *Exited* o *Restarting* | Revisa el motivo con `docker compose logs <servicio>` y luego ejecuta `docker compose restart <servicio>` |
| Cambié código y no se ve | Reconstruye ese servicio: `docker compose up --build -d <servicio>` |
| El QR no abre en el celular | El celular debe estar en la misma red Wi-Fi. Genera el QR con la IP de la computadora (por ejemplo, `http://192.168.1.37:5173`), no con `localhost` |

### Pruebas
```bash
docker compose exec <servicio> sh -c "pip install -q -r requirements-test.txt && pytest -q"
```
La integración continua (`.github/workflows/ci.yml`) corre las pruebas en cada cambio.

---

## 🏗️ Arquitectura

<div align="center"><img src="docs/diagramas/arquitectura_contenedores.png" alt="Arquitectura de contenedores" width="85%"></div>

| Componente | Responsabilidad |
|---|---|
| `auth-service` | Usuarios, roles, contraseñas con hash, JWT y bloqueo temporal |
| `fleet-core-service` | Vehículos, conductores, viajes, gastos, mantenimiento, costos fijos y de personal, despacho QR |
| `reporting-service` | Tablero, modelo de costos, ranking AHP y reportes. No tiene base propia: consulta a `fleet-core-service` con el token del usuario |
| `gateway` (Nginx) | Punto único de entrada (`/api/auth`, `/api/fleet`, `/api/reports`), límite de solicitudes y HTTPS en producción |
| `postgres` | Una instancia con los esquemas `auth` y `fleet`, cada uno con su propio rol |
| `frontend` | React + TypeScript + Vite: el panel web y el portal móvil del conductor |

**Por qué microservicios.** Se compararon tres estilos con una matriz ponderada:

| Estilo | Puntaje |
|---|---|
| **Microservicios** | **3,95** |
| Monolito modular | 3,60 |
| Monolito en capas | 3,35 |

Los microservicios ganan por el **aislamiento de los datos personales** y por el **despliegue independiente** de cada servicio. No ganan por rendimiento: en rendimiento y en costo de operación gana el monolito.

| Producción local con HTTPS (verificado) | Cloud Run (propuesto, no desplegado) |
|:---:|:---:|
| <img src="docs/diagramas/despliegue_b_produccion_local.png" alt="Despliegue local"> | <img src="docs/diagramas/despliegue_c_cloud_run_propuesto.png" alt="Despliegue Cloud Run"> |

## 📐 Diseño UML y modelo de datos

<details open><summary><b>Casos de uso</b></summary><br><img src="docs/diagramas/casos_de_uso.png" alt="Casos de uso"></details>
<details><summary><b>Secuencia: ranking AHP de mantenimientos</b></summary><br><img src="docs/diagramas/secuencia_ranking_ahp.png" alt="Secuencia ranking AHP"></details>
<details><summary><b>Secuencia: emisión y despacho por código QR</b></summary><br><img src="docs/diagramas/secuencia_emision_qr.png" alt="Emisión QR"><img src="docs/diagramas/secuencia_despacho_qr.png" alt="Despacho QR"></details>
<details><summary><b>Secuencia: cierre del viaje y alerta de mantenimiento</b></summary><br><img src="docs/diagramas/secuencia_cierre_viaje_alerta.png" alt="Cierre de viaje"></details>
<details><summary><b>Colaboración y estados</b></summary><br><img src="docs/diagramas/colaboracion_registrar_gasto.png" alt="Colaboración"><img src="docs/diagramas/estados_viaje.png" alt="Estados del viaje"></details>
<details><summary><b>Actividades y flujo de trabajo por carriles</b></summary><br><img src="docs/diagramas/actividades_flujo_operativo.png" alt="Actividades"><img src="docs/diagramas/flujo_trabajo_carriles.png" alt="Flujo de trabajo"></details>
<details><summary><b>Modelo entidad-relación (9 tablas)</b></summary><br><img src="docs/diagramas/modelo_entidad_relacion_1.png" alt="ER parte 1"><img src="docs/diagramas/modelo_entidad_relacion_2.png" alt="ER parte 2"></details>

## 🧮 Priorización con AHP

| Criterio | Peso |
|---|:---:|
| 🛡️ Seguridad (criticidad del tipo de mantenimiento) | **0,528** |
| ⏱️ Urgencia por kilometraje | **0,420** |
| 💲 Costo estimado | **0,053** |

- **Juicios de expertos:** cuestionario aplicado a 3 expertos externos del transporte de carga. Los pesos son la media geométrica de los 2 expertos con juicios consistentes; el tercero (CR = 0,54) quedó pendiente de revisar sus juicios, según el protocolo.
- **Consistencia:** razón de consistencia CR = **0,0115**, menor que 0,10, verificada también con la librería **ahpy**. **El servicio no arranca** si la matriz es inconsistente (CR ≥ 0,10).
- **Criticidad:** con la mediana de las calificaciones de los expertos, frenos, llantas, bocines, aceite y filtros quedan igual de críticos; a igual puntaje se atiende primero el mantenimiento más vencido en kilómetros.
- **Estabilidad:** el primer lugar y el top-3 se mantienen con cambios de ±30 % en los pesos (τ de Kendall mínima de 0,935).
- **Configuración:** `services/reporting-service/app/dashboards/ahp_config.json`, con la procedencia de cada valor.

## ✅ Pruebas y calidad

| Servicio | Pruebas | Aprobadas | Omitidas |
|---|:---:|:---:|:---:|
| auth-service | 89 | 89 | 0 |
| fleet-core-service | 546 | 545 | 1* |
| reporting-service | 275 | 275 | 0 |
| **Total** | **910** | **909** | **1** |

<sub>* La prueba del límite de intentos del QR bloquea el gateway durante un minuto; solo corre con `RUN_RATE_LIMIT_TESTS=1`.</sub>

- **Pruebas de integración:** envían peticiones HTTP reales a través del gateway, con autenticación y roles.
- **Cobertura:** 80 % (de 69 a 94 % por servicio).
- **Carga (k6):** p95 de 1,19 s con 10 usuarios a la vez.
- **Benchmark con un millón de viajes:** las consultas por vehículo o por viaje son de 6 a 10 veces más rápidas con índices.
- **Validación con un mes de datos reales** de la empresa caso: el costo total calculado por el sistema difiere en −0,48 % del cálculo manual, y la utilidad en +0,64 %.

## 📁 Mapa del repositorio

```
control_flota/
├── docker-compose.yml          # entorno local completo
├── docker-compose.prod.yml     # producción local con HTTPS
├── infra/                      # nginx (gateway) y postgres (un rol por servicio)
├── services/
│   ├── auth-service/           # usuarios, roles y JWT
│   ├── fleet-core-service/     # flota, viajes, gastos, mantenimiento, costos y QR
│   └── reporting-service/      # tablero, costos, AHP y reportes
├── frontend/                   # React + TypeScript: panel y portal del conductor
├── scripts/                    # datos de prueba, informes, benchmark, carga y capturas del README
├── docs/                       # banner, capturas, diagramas y videos
├── .tours/                     # recorridos guiados del código (CodeTour)
└── flotacontrol.code-workspace # espacio de trabajo de VS Code
```

### Recorrido guiado del código

Abra `flotacontrol.code-workspace` en VS Code e instale la extensión recomendada **CodeTour**. Cada recorrido abre los archivos clave en la línea exacta, en este orden:

| Recorrido | Qué muestra | Dónde |
|---|---|---|
| 1 · Arquitectura | Contenedores, base de datos con un rol por servicio y rutas del gateway | `docker-compose.yml`, `infra/` |
| 2 · auth-service | bcrypt, emisión del JWT, login y bloqueo por intentos | `services/auth-service/app/` |
| 3 · fleet-core-service | Módulos del dominio, roles, cierre de viaje con alertas, despacho QR, agregaciones | `services/fleet-core-service/app/` |
| 4 · reporting-service | Cliente HTTP hacia fleet-core, modelo de costos y AHP | `services/reporting-service/app/` |
| 5 · Frontend | Rutas, conexión con el gateway, sesión y pantallas principales | `frontend/src/` |
| 6 · Pruebas | Pruebas unitarias, de integración e integración continua | `services/*/tests/`, `.github/workflows/` |

## 🗺️ Alcance y trabajo futuro

- **Fuera del alcance:**
  - GPS en tiempo real;
  - SMS o WhatsApp;
  - vencimiento de documentos (SOAT, matrícula);
  - facturación electrónica;
  - mantenimiento basado en sensores.
- **Siguiente etapa:**
  - registrar la comisión del conductor como porcentaje del flete de cada viaje (práctica de la empresa caso);
  - completar el panel AHP con la revisión del tercer experto y ampliarlo a 5 expertos;
  - registrar el kilometraje de cada viaje para medir el costo por kilómetro de la empresa caso;
  - pruebas con usuarios (tareas cronometradas y SUS);
  - despliegue en Cloud Run.

## 👩‍💻 Autora

**Rosa Margarita Vivanco Vélez** · Ingeniería en Tecnologías de la Información, Universidad Estatal de Milagro (UNEMI). Tutoras: M.Sc. Mirella Azucena Peralta Correa y M.Sc. María Gabriela Espinoza Bravo. Ver `AUTHORS`.

---

<div align="center">
<sub>© 2026 <b>Rosa Margarita Vivanco Vélez</b> · Universidad Estatal de Milagro · Trabajo de titulación con fines académicos.</sub>
</div>
