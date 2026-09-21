# frontend

SPA en React + TypeScript + Vite. Consume el gateway (`/api/auth`,
`/api/fleet`, `/api/reports`) definido en `infra/nginx/nginx.conf`. El único
backend que puede llamar directo el celular de un conductor sin sesión es
`/api/fleet/despacho/*` (RF-18); todo lo demás exige un token JWT obtenido
en `/login`.

## Estructura

```
src/
├── main.tsx              # punto de entrada: monta <App/> con router + AuthProvider
├── App.tsx                # mapa de rutas (react-router-dom)
├── nav.ts                  # los 7 módulos del menú lateral (Costos y Usuarios, solo administrador)
├── context/
│   └── AuthContext.tsx      # sesión (token + usuario), persistida en localStorage
├── pages/                   # una pantalla por ruta -- ver detalle abajo
├── components/               # AppShell (layout), Modal, Logo, ProtectedRoute, PlotFigure
├── charts/
│   └── expensePlots.ts        # gráficas del dashboard (Observable Plot)
├── services/                   # clientes HTTP hacia cada microservicio
├── types/                       # tipos TS, reflejo a mano de los esquemas Pydantic
└── utils/
    └── tax.ts                     # tarifas de IVA (Ecuador) para el desglose de gastos
```

## Páginas (`src/pages/`)

| Página | Ruta | Qué hace |
|---|---|---|
| `LoginPage` | `/login` | RF-02: inicio de sesión |
| `DashboardPage` | `/` | RF-15, RF-16, RF-19: KPIs, gráficas y priorización AHP interactiva |
| `VehiclesPage` | `/vehiculos` | RF-04: alta/edición/consulta de vehículos |
| `DriversPage` | `/conductores` | RF-05: alta/edición de conductores + código QR de despacho |
| `TripsPage` / `TripDetailPage` | `/viajes`, `/viajes/:id` | RF-06, RF-07, RF-14: viajes, gastos, cierre |
| `MaintenancePage` | `/mantenimiento` | RF-11 a RF-13, RF-20: mantenimiento y ranking AHP |
| `ReportsPage` | `/reportes` | RF-17: reporte detallado y exportación a Excel/PDF |
| `UsersPage` | `/usuarios` | RF-01, RF-03: gestión de usuarios (solo admin) |
| `ProfilePage` | `/perfil` | Datos del usuario en sesión |
| `DespachoPage` | `/despacho?driverId=&token=` | RF-18: portal móvil del conductor, sin sesión |

`DespachoPage` es la única página fuera de `ProtectedRoute` junto a
`LoginPage` (ver `App.tsx`) — se abre desde un código QR, no desde el menú.

## Variables de entorno

`VITE_API_BASE_URL` (opcional). Si no se define, el cliente HTTP
(`services/apiClient.ts`) deriva la URL del gateway del propio host con el
que el navegador cargó la página
(`` `http://${window.location.hostname}:8080/api` ``) — **nunca uses un
`localhost` fijo**: si el conductor abre el enlace del QR desde la IP de
red local del panel de administración, las llamadas a la API tienen que ir
a esa misma IP, no a `localhost` (que en su celular se refiere al propio
celular).

## Desarrollo local sin Docker

```bash
npm install
npm run dev      # Vite, puerto 5173
npm run build    # tsc -b && vite build
```
