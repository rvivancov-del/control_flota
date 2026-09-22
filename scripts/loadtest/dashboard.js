// Prueba de carga del tablero (RNF-01: consultas en menos de 2 s con hasta 10 usuarios concurrentes).
//
// Cada usuario virtual hace lo que hace el navegador al abrir el tablero del administrador: dispara en
// paralelo las consultas del panel principal (resumen del período y del anterior, registros, tendencia,
// estado de mantenimiento, conductores, rutas, ranking de atención, política de alertas y metodología de
// costos) y las de las listas operativas (vehículos, viajes, gastos); luego espera y repite, como la
// actualización periódica de la pantalla.
//
// Uso (con la pila de verificación en :18080; ver scripts/loadtest/README.md):
//   k6 run -e BASE_URL=http://host.docker.internal:18080/api scripts/loadtest/dashboard.js
//
// Variables: BASE_URL, LOAD_USER, LOAD_PASSWORD, VUS (10), DURATION (60s), THINK_SECONDS (5),
// DATE_FROM y DATE_TO (por defecto, el mes en curso hasta hoy).
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://host.docker.internal:18080/api";
const USER = __ENV.LOAD_USER || "admin";
const PASS = __ENV.LOAD_PASSWORD || "Admin1234";
const VUS = Number(__ENV.VUS || 10);
const DURATION = __ENV.DURATION || "60s";
const THINK = Number(__ENV.THINK_SECONDS || 5);

function iso(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
const today = new Date();
const DATE_FROM = __ENV.DATE_FROM || iso(new Date(today.getFullYear(), today.getMonth(), 1));
const DATE_TO = __ENV.DATE_TO || iso(today);
const PREV_FROM = iso(new Date(today.getFullYear(), today.getMonth() - 1, 1));
const PREV_TO = iso(new Date(today.getFullYear(), today.getMonth() - 1, Math.min(today.getDate(), 28)));
const period = `date_from=${DATE_FROM}&date_to=${DATE_TO}`;

// Consultas del tablero: nombre (para las métricas) y ruta.
const QUERIES = [
  ["summary", `/reports/dashboard/summary?${period}`],
  ["summary_prev", `/reports/dashboard/summary?date_from=${PREV_FROM}&date_to=${PREV_TO}`],
  ["records", `/reports/dashboard/records?${period}`],
  ["trend", `/reports/dashboard/trend?period=month&date_to=${DATE_TO}`],
  ["maintenance_status", "/reports/dashboard/maintenance-status"],
  ["drivers", `/reports/dashboard/drivers?${period}`],
  ["routes", `/reports/dashboard/routes?${period}`],
  ["vehicle_attention", `/reports/dashboard/vehicle-attention?urgency_over_cost=3&${period}`],
  ["cost_model", "/reports/dashboard/cost-model"],
  ["maintenance_policy", "/fleet/maintenance/policy"],
  ["vehicles", "/fleet/vehicles"],
  ["trips", `/fleet/trips?${period}`],
  ["expenses", `/fleet/expenses?${period}`],
];

const carga = new Trend("carga_tablero_ms", true); // hasta que llega la última respuesta del tablero

export const options = {
  scenarios: { tablero: { executor: "constant-vus", vus: VUS, duration: DURATION } },
  thresholds: Object.assign(
    { http_req_failed: ["rate<0.01"], checks: ["rate>0.99"], carga_tablero_ms: ["p(95)<2000"] },
    ...QUERIES.map(([name]) => ({ [`http_req_duration{name:${name}}`]: ["p(95)<2000"] })),
  ),
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "max"],
};

export function setup() {
  const res = http.post(`${BASE}/auth/login`, JSON.stringify({ username: USER, password: PASS }), {
    headers: { "Content-Type": "application/json" },
  });
  if (res.status !== 200) {
    throw new Error(`No se pudo iniciar sesión como ${USER}: HTTP ${res.status}`);
  }
  return { token: res.json("access_token") };
}

export default function (data) {
  const headers = { Authorization: `Bearer ${data.token}` };
  const started = Date.now();
  const responses = http.batch(QUERIES.map(([name, path]) => ["GET", `${BASE}${path}`, null, { headers, tags: { name } }]));
  carga.add(Date.now() - started);
  responses.forEach((r, i) => {
    check(r, { [`${QUERIES[i][0]} responde 200`]: (x) => x.status === 200 });
  });
  sleep(THINK);
}
