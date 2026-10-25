/**
 * Ruta /reportes · admin exporta, operador consulta · RF-17.
 * Reporte de mantenimientos y de costos del período, con exportación a Excel y PDF.
 * API: reporting-service (/api/reports/*).
 */
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AppShell from "../components/AppShell";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { reportsApi } from "../services/reportsApi";
import type { Vehicle } from "../types/fleet";
import type { DashboardSummary, IvaMode } from "../types/dashboard";
import type { MaintenanceReportItem, ReportFilters, TrendResponse } from "../types/reports";
import styles from "./ReportsPage.module.css";

const currency = new Intl.NumberFormat("es-EC", { style: "currency", currency: "USD" });

const TYPE_LABELS: Record<string, string> = {
  aceite: "Aceite",
  filtros: "Filtros",
  llantas: "Llantas",
  frenos: "Frenos",
  bocines: "Bocines",
  otro: "Otro",
};

const STATUS_LABELS: Record<string, string> = {
  pendiente: "Pendiente",
  en_proceso: "En proceso",
  completado: "Completado",
};

async function downloadAuthenticated(url: string, token: string, filename: string) {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) return;
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

/** RF-17: reporte detallado de mantenimientos y exportación de costos a Excel/PDF.
 * RF-03: ambos roles consultan; solo el administrador exporta. */
function ReportsPage() {
  const { token, isAdmin } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [filters, setFilters] = useState<ReportFilters>({});
  const [period, setPeriod] = useState<"week" | "month">("month");
  // Montos tal como se pagaron (con IVA) o sin IVA: mismo interruptor que el tablero.
  const [ivaMode, setIvaMode] = useState<IvaMode>("bruto");

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trend, setTrend] = useState<TrendResponse | null>(null);
  const [maintenanceItems, setMaintenanceItems] = useState<MaintenanceReportItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    fleetApi.listVehicles(token).then(setVehicles).catch(() => undefined);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    const query = { ...filters, iva_mode: ivaMode };
    Promise.all([
      reportsApi.summary(token, query),
      reportsApi.trend(token, period, query),
      reportsApi.maintenanceReport(token, query),
    ])
      .then(([summaryData, trendData, maintenanceData]) => {
        setSummary(summaryData);
        setTrend(trendData);
        setMaintenanceItems(maintenanceData);
      })
      .catch(() => setError("No se pudo cargar el reporte. Verifica que fleet-core-service esté disponible."))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, period, ivaMode, filters.vehicle_id, filters.date_from, filters.date_to]);

  const chartData = (trend?.points ?? []).map((p) => ({
    periodo: p.period_label,
    Total: Number(p.total_cost),
  }));

  const averageCost = useMemo(() => {
    if (chartData.length === 0) return 0;
    return chartData.reduce((acc, p) => acc + p.Total, 0) / chartData.length;
  }, [chartData]);

  const axisStyle = { fontSize: 12, fill: "var(--chart-axis)", fontFamily: "var(--font-mono)" };

  return (
    <AppShell title="Reportes">
      <div className={styles.grid}>
        <div className={styles.panel}>
          <div className={styles.filterBar}>
            <div className={styles.filterField}>
              <label htmlFor="vehicle_id">Vehículo</label>
              <select
                id="vehicle_id"
                value={filters.vehicle_id ?? ""}
                onChange={(e) => setFilters({ ...filters, vehicle_id: e.target.value || undefined })}
              >
                <option value="">Toda la flota</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plate}
                  </option>
                ))}
              </select>
            </div>
            <div className={styles.filterField}>
              <label htmlFor="date_from">Desde</label>
              <input
                id="date_from"
                type="date"
                value={filters.date_from ?? ""}
                onChange={(e) => setFilters({ ...filters, date_from: e.target.value || undefined })}
              />
            </div>
            <div className={styles.filterField}>
              <label htmlFor="date_to">Hasta</label>
              <input
                id="date_to"
                type="date"
                value={filters.date_to ?? ""}
                onChange={(e) => setFilters({ ...filters, date_to: e.target.value || undefined })}
              />
            </div>
            <div className={styles.filterField}>
              <label htmlFor="iva_mode">Montos</label>
              <select id="iva_mode" value={ivaMode} onChange={(e) => setIvaMode(e.target.value as IvaMode)}>
                <option value="bruto">Con IVA (lo pagado)</option>
                <option value="neto">Sin IVA (neto)</option>
              </select>
            </div>
            {isAdmin && (
              <div className={styles.exportRow}>
                <button
                  type="button"
                  className={styles.exportButton}
                  onClick={() =>
                    token &&
                    downloadAuthenticated(reportsApi.exportUrl({ ...filters, iva_mode: ivaMode }), token, "reporte_costos.xlsx")
                  }
                >
                  Excel
                </button>
                <button
                  type="button"
                  className={styles.exportButtonSecondary}
                  onClick={() =>
                    token &&
                    downloadAuthenticated(reportsApi.exportPdfUrl({ ...filters, iva_mode: ivaMode }), token, "reporte_costos.pdf")
                  }
                >
                  PDF
                </button>
              </div>
            )}
          </div>
          {isAdmin && (
            <p className={styles.exportHint}>
              {filters.date_from && filters.date_to
                ? "El archivo incluye los costos fijos y de personal prorrateados a este período (costo total, utilidad y margen)."
                : "Elige «Desde» y «Hasta» para que el archivo incluya los costos fijos y de personal; sin período solo lleva los costos variables."}
            </p>
          )}
        </div>

        {error && <p className={styles.empty}>{error}</p>}

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Costos por vehículo</span>
          </div>
          {summary && summary.vehicles.length > 0 ? (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Placa</th>
                  <th>Viajes</th>
                  <th>Combustible</th>
                  <th>Peajes</th>
                  <th>Alimentación</th>
                  <th>Mantenimiento</th>
                  <th>Gasto operativo</th>
                </tr>
              </thead>
              <tbody>
                {summary.vehicles.map((v) => (
                  <tr key={v.vehicle_id}>
                    <td className="mono">{v.plate}</td>
                    <td className="mono">{v.trip_count}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.combustible))}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.peaje))}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.alimentacion))}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.mantenimiento))}</td>
                    <td className="mono">{currency.format(Number(v.total_cost))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "No hay datos para este filtro."}</p>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Tendencia de costos en el tiempo</span>
            <div className={styles.periodToggle}>
              <button
                type="button"
                className={`${styles.periodButton} ${period === "week" ? styles.periodButtonActive : ""}`}
                onClick={() => setPeriod("week")}
              >
                Por semana
              </button>
              <button
                type="button"
                className={`${styles.periodButton} ${period === "month" ? styles.periodButtonActive : ""}`}
                onClick={() => setPeriod("month")}
              >
                Por mes
              </button>
            </div>
          </div>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={chartData} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--brand-accent)" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="var(--brand-accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="periodo" tick={axisStyle} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
                <YAxis
                  tick={axisStyle}
                  tickLine={false}
                  axisLine={false}
                  width={64}
                  tickFormatter={(value: number) => currency.format(value).replace(/\.00$/, "")}
                />
                <Tooltip
                  formatter={(value: number) => currency.format(value)}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid var(--line)",
                    boxShadow: "var(--shadow-card)",
                    fontSize: 13,
                  }}
                />
                {averageCost > 0 && (
                  <ReferenceLine
                    y={averageCost}
                    stroke="var(--chart-mantenimiento)"
                    strokeDasharray="5 4"
                    label={{
                      value: `Promedio ${currency.format(averageCost)}`,
                      position: "insideTopRight",
                      fill: "var(--chart-mantenimiento)",
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  />
                )}
                <Area type="monotone" dataKey="Total" stroke="none" fill="url(#trendFill)" isAnimationActive={false} />
                <Line
                  type="monotone"
                  dataKey="Total"
                  stroke="var(--brand-accent)"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: "var(--surface)", stroke: "var(--brand-accent)", strokeWidth: 2 }}
                  activeDot={{ r: 6 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "No hay viajes completados en este rango."}</p>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Mantenimientos del período</span>
          </div>
          {maintenanceItems.length > 0 ? (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Vehículo</th>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th>Km programado</th>
                  <th>Fecha</th>
                  <th>Costo</th>
                </tr>
              </thead>
              <tbody>
                {maintenanceItems.map((m, idx) => (
                  <tr key={idx}>
                    <td className="mono">{m.vehicle_plate}</td>
                    <td>{TYPE_LABELS[m.maintenance_type] ?? m.maintenance_type}</td>
                    <td>{STATUS_LABELS[m.status] ?? m.status}</td>
                    <td className="mono">{m.scheduled_mileage_km?.toLocaleString("es-EC") ?? "—"}</td>
                    <td className="mono">{m.performed_at ?? "—"}</td>
                    <td className="mono">{m.cost ? currency.format(Number(m.cost)) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "No hay mantenimientos en este rango."}</p>
          )}
        </div>
      </div>
    </AppShell>
  );
}

export default ReportsPage;
