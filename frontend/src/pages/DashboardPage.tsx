import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  DollarSign,
  Fuel,
  Gauge,
  MapPin,
  PieChart,
  TrendingUp,
  Users,
  Wrench,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AppShell from "../components/AppShell";
import PlotFigure from "../components/PlotFigure";
import {
  buildHistogramPlot,
  buildMaintenanceMixPlot,
  buildRouteCostPlot,
  buildScatterPlot,
  buildTrendPlot,
  trendPlotHeight,
} from "../charts/expensePlots";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { reportsApi } from "../services/reportsApi";
import { NAV_ITEMS } from "../nav";
import type { DashboardSummary, IvaMode } from "../types/dashboard";
import type {
  CostModelInfo,
  DriverSummaryResponse,
  ExpenseCategory,
  ExpenseRecord,
  MaintenanceStatus,
  RouteSummaryResponse,
  TrendPoint,
  VehicleAttentionResponse,
} from "../types/reports";
import styles from "./DashboardPage.module.css";

const POLL_INTERVAL_MS = 20_000;
/** Períodos históricos mínimos para estimar un rango de incertidumbre de la
 * proyección — con menos, la variabilidad observada es ruido, no una señal. */
const MIN_PERIODS_FOR_RANGE = 3;

const currency = new Intl.NumberFormat("es-EC", { style: "currency", currency: "USD" });
const currencyCompact = new Intl.NumberFormat("es-EC", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

type CategoryOption = { value: ExpenseCategory | ""; label: string; color: string };

const CATEGORY_OPTIONS: CategoryOption[] = [
  { value: "", label: "Gasto operativo total", color: "var(--brand-navy)" },
  { value: "combustible", label: "Combustible", color: "var(--chart-combustible)" },
  { value: "peaje", label: "Peajes", color: "var(--chart-peaje)" },
  { value: "alimentacion", label: "Alimentación", color: "var(--chart-alimentacion)" },
  { value: "mantenimiento", label: "Mantenimiento", color: "var(--chart-mantenimiento)" },
];

const MAINT_TYPE_LABELS: Record<string, string> = {
  aceite: "Aceite",
  filtros: "Filtros",
  llantas: "Llantas",
  frenos: "Frenos",
  bocines: "Bocines",
  otro: "Otro",
};

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function toDateInput(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

type Granularity = "week" | "month" | "year";

function parseLocalDate(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Días (inclusive) entre dos fechas AAAA-MM-DD. */
function daysInclusive(from: string, to: string): number {
  return Math.round((parseLocalDate(to).getTime() - parseLocalDate(from).getTime()) / 86_400_000) + 1;
}

/** Los primeros `days` días de un período (sin pasarse de su fin). */
function firstDays(bounds: { date_from: string; date_to: string }, days: number): { date_from: string; date_to: string } {
  const start = parseLocalDate(bounds.date_from);
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + days - 1);
  const cap = parseLocalDate(bounds.date_to);
  return { date_from: bounds.date_from, date_to: toDateInput(end < cap ? end : cap) };
}

const GRANULARITY_OPTIONS: { value: Granularity; label: string }[] = [
  { value: "week", label: "Semana" },
  { value: "month", label: "Mes" },
  { value: "year", label: "Año" },
];

/** Lunes de la semana de `d`, a medianoche local. */
function startOfWeek(d: Date): Date {
  const dayIdx = (d.getDay() + 6) % 7; // lunes = 0
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() - dayIdx);
}

/** Límites del período seleccionado, en la zona horaria local — evita el
 * corrimiento de día que da toISOString() cerca de medianoche en UTC-5.
 * offset=0 es el período en curso (recortado a hoy); offset negativo, uno
 * anterior completo. */
function periodBounds(granularity: Granularity, offset: number): { date_from: string; date_to: string } {
  const now = new Date();
  if (granularity === "week") {
    const start = startOfWeek(now);
    start.setDate(start.getDate() + offset * 7);
    const naturalEnd = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
    const end = offset === 0 ? now : naturalEnd;
    return { date_from: toDateInput(start), date_to: toDateInput(end) };
  }
  if (granularity === "year") {
    const year = now.getFullYear() + offset;
    const start = new Date(year, 0, 1);
    const end = offset === 0 ? now : new Date(year, 11, 31);
    return { date_from: toDateInput(start), date_to: toDateInput(end) };
  }
  const start = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const end = offset === 0 ? now : new Date(start.getFullYear(), start.getMonth() + 1, 0);
  return { date_from: toDateInput(start), date_to: toDateInput(end) };
}

function periodLabel(granularity: Granularity, offset: number): string {
  const now = new Date();
  if (granularity === "week") {
    const start = startOfWeek(now);
    start.setDate(start.getDate() + offset * 7);
    const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
    const fmt = (d: Date) => `${d.getDate()}/${d.getMonth() + 1}`;
    return `Semana del ${fmt(start)} al ${fmt(end)}`;
  }
  if (granularity === "year") {
    return String(now.getFullYear() + offset);
  }
  const base = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const label = base.toLocaleDateString("es-EC", { month: "long", year: "numeric" });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

/** Cuánto del período ya transcurrió — un período pasado siempre está
 * 100% transcurrido, así que la "proyección" de un período cerrado
 * coincide exactamente con su total real (sin necesidad de un caso aparte). */
function periodProgress(granularity: Granularity, isCurrent: boolean): { elapsed: number; total: number } {
  const now = new Date();
  if (granularity === "week") {
    const total = 7;
    return { elapsed: isCurrent ? ((now.getDay() + 6) % 7) + 1 : total, total };
  }
  if (granularity === "year") {
    const year = now.getFullYear();
    const isLeap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
    const total = isLeap ? 366 : 365;
    if (!isCurrent) return { elapsed: total, total };
    const start = new Date(year, 0, 1);
    const elapsed = Math.floor((now.getTime() - start.getTime()) / 86_400_000) + 1;
    return { elapsed, total };
  }
  const total = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  return { elapsed: isCurrent ? now.getDate() : total, total };
}

/** Opciones de la escala de comparación pareada de Saaty (AHP) para la razón
 * "¿cuánto más importante es la urgencia de mantenimiento frente al costo?".
 * El valor viaja al backend (GET /reports/dashboard/vehicle-attention), que
 * deriva los pesos y calcula el ranking con el mismo motor de RF-20. */
const SAATY_OPTIONS = [
  { value: 1, label: "Igual de importantes" },
  { value: 2, label: "Un poco más importante la urgencia" },
  { value: 3, label: "Moderadamente más importante la urgencia" },
  { value: 5, label: "Bastante más importante la urgencia" },
  { value: 7, label: "Mucho más importante la urgencia" },
  { value: 9, label: "La urgencia es lo único que importa" },
];

/** RF-15, RF-16, RF-19: panel principal -- KPIs del período, gráficas de
 * costo/tendencia, priorización de mantenimiento interactiva (AHP de 2
 * criterios) y las tablas de vehículos, conductores y rutas. */
function DashboardPage() {
  const { token, user, isAdmin } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [records, setRecords] = useState<ExpenseRecord[]>([]);
  const [trendPoints, setTrendPoints] = useState<TrendPoint[]>([]);
  const [maintenanceStatus, setMaintenanceStatus] = useState<MaintenanceStatus | null>(null);
  const [previousPeriodSummary, setPreviousPeriodSummary] = useState<DashboardSummary | null>(null);
  const [driverSummary, setDriverSummary] = useState<DriverSummaryResponse | null>(null);
  const [routeSummary, setRouteSummary] = useState<RouteSummaryResponse | null>(null);
  const [attention, setAttention] = useState<VehicleAttentionResponse | null>(null);
  // Umbral 'próximo' (km) de la política única de RF-13, que decide fleet-core-service.
  const [proximoKm, setProximoKm] = useState<number | null>(null);
  const [category, setCategory] = useState<ExpenseCategory | "">("");
  // Fase 3: montos pagados (con IVA, "bruto") o sin IVA ("neto"); metodología y estado de las tarifas.
  const [ivaMode, setIvaMode] = useState<IvaMode>("bruto");
  const [costModel, setCostModel] = useState<CostModelInfo | null>(null);
  const [granularity, setGranularity] = useState<Granularity>("month");
  const [periodOffset, setPeriodOffset] = useState(0);
  const [urgencyOverCost, setUrgencyOverCost] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isCurrentPeriod = periodOffset === 0;
  const current = periodBounds(granularity, periodOffset);
  const previous = periodBounds(granularity, periodOffset - 1);
  // Un período en curso está a medias: se compara con los MISMOS días del período anterior, no con el anterior
  // completo (antes, a mitad de mes la variación salía casi siempre negativa).
  const previousComparable = isCurrentPeriod
    ? firstDays(previous, daysInclusive(current.date_from, current.date_to))
    : previous;

  useEffect(() => {
    setPeriodOffset(0);
  }, [granularity]);

  useEffect(() => {
    if (!token) return;
    const iva = { iva_mode: ivaMode };
    const filters = category ? { category, ...current, ...iva } : { ...current, ...iva };
    const previousFilters = category ? { category, ...previousComparable, ...iva } : { ...previousComparable, ...iva };
    const trendFilters = category ? { category, date_to: current.date_to, ...iva } : { date_to: current.date_to, ...iva };
    let cancelled = false;

    const load = (showLoading: boolean) => {
      if (showLoading) setIsLoading(true);
      Promise.all([
        reportsApi.summary(token, filters),
        reportsApi.records(token, filters),
        reportsApi.trend(token, granularity, trendFilters),
        reportsApi.maintenanceStatus(token, iva),
        reportsApi.summary(token, previousFilters),
        reportsApi.drivers(token, filters),
        reportsApi.routes(token, { ...current, ...iva }),
      ])
        .then(([summaryData, recordsData, trendData, maintenanceData, previousData, driversData, routesData]) => {
          if (cancelled) return;
          setSummary(summaryData);
          setRecords(recordsData);
          setTrendPoints(trendData.points);
          setMaintenanceStatus(maintenanceData);
          setPreviousPeriodSummary(previousData);
          setDriverSummary(driversData);
          setRouteSummary(routesData);
          setError(null);
        })
        .catch(() => {
          if (!cancelled) setError("No se pudo cargar el dashboard. Verifica que fleet-core-service esté disponible.");
        })
        .finally(() => {
          if (!cancelled && showLoading) setIsLoading(false);
        });
    };

    load(true);
    const interval = setInterval(() => load(false), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token, category, granularity, periodOffset, ivaMode]);

  // Metodología del modelo de costos (categorías, fórmulas, fuentes y estado de las tarifas de IVA).
  useEffect(() => {
    if (!token) return;
    reportsApi
      .costModel(token)
      .then((info) => {
        setCostModel(info);
        setIvaMode(info.iva.modo_por_defecto);
      })
      .catch(() => setCostModel(null));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    fleetApi
      .maintenancePolicy(token)
      .then((policy) => setProximoKm(policy.proximo_km))
      .catch(() => setProximoKm(null));
  }, [token]);

  // RF-19: el ranking de atención lo calcula el backend (mismo motor y misma
  // escala de urgencia que RF-20); se vuelve a pedir al mover la razón de Saaty.
  useEffect(() => {
    if (!token) return;
    const filters = category ? { category, ...current } : { ...current };
    let cancelled = false;
    const loadAttention = () => {
      reportsApi
        .vehicleAttention(token, urgencyOverCost, filters)
        .then((data) => {
          if (!cancelled) setAttention(data);
        })
        .catch(() => {
          if (!cancelled) setAttention(null);
        });
    };
    loadAttention();
    const interval = setInterval(loadAttention, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token, category, granularity, periodOffset, urgencyOverCost]);

  const handleExport = async () => {
    if (!token) return;
    const response = await fetch(reportsApi.exportUrl({ ...current, iva_mode: ivaMode }), {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "reporte_costos.xlsx";
    link.click();
    URL.revokeObjectURL(url);
  };

  const activeOption = CATEGORY_OPTIONS.find((opt) => opt.value === category) ?? CATEGORY_OPTIONS[0];

  const chartData =
    summary?.vehicles.map((v) => ({
      placa: v.plate,
      Combustible: Number(v.breakdown.combustible),
      Peajes: Number(v.breakdown.peaje),
      Alimentación: Number(v.breakdown.alimentacion),
      Mantenimiento: Number(v.breakdown.mantenimiento),
      seleccionado: Number(v.total_cost),
    })) ?? [];

  const axisStyle = useMemo(() => ({ fontSize: 12, fill: "var(--ink)", fontFamily: "var(--font-mono)" }), []);

  // KPI 1: variación vs. el período anterior (misma granularidad)
  const variationPct = useMemo(() => {
    if (!summary || !previousPeriodSummary) return null;
    const curr = Number(summary.fleet_total_cost);
    const prev = Number(previousPeriodSummary.fleet_total_cost);
    if (prev === 0) return null;
    return ((curr - prev) / prev) * 100;
  }, [summary, previousPeriodSummary]);

  // KPI 2: proyección de cierre del período al ritmo actual — si el período
  // ya cerró, "transcurrido" = "total" y la proyección coincide con el real.
  const progress = periodProgress(granularity, isCurrentPeriod);
  const projectedClose = useMemo(() => {
    if (!summary || progress.elapsed === 0) return null;
    return (Number(summary.fleet_total_cost) / progress.elapsed) * progress.total;
  }, [summary, progress.elapsed, progress.total]);

  // Rango de incertidumbre de la proyección, a partir de cuánto varió
  // realmente el gasto entre períodos pasados (coeficiente de variación) —
  // un solo número sugiere una certeza que "asumir ritmo uniforme" no tiene.
  const projectedCloseRange = useMemo(() => {
    // Solo períodos completos: el que está en curso (a medias) inflaría la variabilidad observada.
    const completed = trendPoints.filter((p) => p.period_start !== null && p.period_start < current.date_from);
    if (projectedClose === null || !isCurrentPeriod || completed.length < MIN_PERIODS_FOR_RANGE) return null;
    const values = completed.map((p) => Number(p.total_cost));
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    if (mean === 0) return null;
    const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length;
    const cv = Math.sqrt(variance) / mean;
    return { low: projectedClose * Math.max(0, 1 - cv), high: projectedClose * (1 + cv) };
  }, [projectedClose, isCurrentPeriod, trendPoints]);

  // KPI 3: costo por kilómetro de toda la flota (eficiencia)
  const fleetDistanceKm = summary?.vehicles.reduce((acc, v) => acc + v.distance_km, 0) ?? 0;
  // Fase 3: costos e indicadores del modelo completo (Ct = Cv + Cf); el operador solo recibe los variables.
  const fleetCosts = summary?.fleet_costs ?? null;
  const fixedIncluded = Boolean(fleetCosts?.fixed_included);
  const numOrNull = (v: string | null | undefined) => (v == null ? null : Number(v));
  const costPerKm = category
    ? summary && fleetDistanceKm > 0
      ? Number(summary.fleet_total_cost) / fleetDistanceKm
      : null
    : numOrNull(fixedIncluded ? fleetCosts?.ct_per_km : fleetCosts?.cv_per_km);
  const costPerKmLabel = category
    ? `Costo por km — ${activeOption.label}`
    : fixedIncluded
      ? "Costo total por kilómetro"
      : "Costo variable por kilómetro";
  const revenueCoverage = numOrNull(fleetCosts?.revenue_coverage_pct);
  const noFixedCostsYet = fixedIncluded && Number(fleetCosts?.fixed_cost ?? 0) === 0;

  // KPI 4: mantenimientos urgentes
  const urgentAlerts = (maintenanceStatus?.alerts ?? []).filter((a) => a.urgency !== "normal");
  const overdueCount = urgentAlerts.filter((a) => a.urgency === "vencido").length;
  const dueSoonCount = urgentAlerts.filter((a) => a.urgency === "proximo").length;

  // KPI 5: margen (rentabilidad) — null si ningún viaje del período tiene ingreso registrado
  const hasRevenueData = summary?.fleet_total_revenue != null;
  const fleetMargin = summary?.fleet_total_margin != null ? Number(summary.fleet_total_margin) : null;
  const fleetRevenue = summary?.fleet_total_revenue != null ? Number(summary.fleet_total_revenue) : null;
  const marginPct = fleetMargin !== null && fleetRevenue && fleetRevenue > 0 ? (fleetMargin / fleetRevenue) * 100 : null;

  // KPI 6: consumo de combustible (L/100km) de toda la flota
  const fleetFuelLiters = summary?.vehicles.reduce((acc, v) => acc + Number(v.fuel_liters), 0) ?? 0;
  const fleetFuelEfficiency = fleetDistanceKm > 0 && fleetFuelLiters > 0 ? (fleetFuelLiters / fleetDistanceKm) * 100 : null;

  // KPI 7: utilización — proxy de disponibilidad a partir de días con actividad registrada
  // (no hay registro real de tiempo en taller; se declara así explícitamente en la UI)
  const utilizationVehicles = (summary?.vehicles ?? []).filter((v) => v.utilization_pct != null);
  const avgUtilization =
    utilizationVehicles.length > 0
      ? utilizationVehicles.reduce((acc, v) => acc + Number(v.utilization_pct), 0) / utilizationVehicles.length
      : null;

  // Composición porcentual (solo tiene sentido en la vista "todos")
  const fleetTotal = Number(summary?.fleet_total_cost ?? 0);
  const categoryTotals = (summary?.vehicles ?? []).reduce(
    (acc, v) => ({
      combustible: acc.combustible + Number(v.breakdown.combustible),
      peaje: acc.peaje + Number(v.breakdown.peaje),
      alimentacion: acc.alimentacion + Number(v.breakdown.alimentacion),
      mantenimiento: acc.mantenimiento + Number(v.breakdown.mantenimiento),
    }),
    { combustible: 0, peaje: 0, alimentacion: 0, mantenimiento: 0 },
  );

  const priorityRanking = attention?.items ?? [];

  return (
    <AppShell title={`Hola, ${user?.full_name ?? user?.username}`}>
      <div className={styles.grid}>
        {error && <p className={styles.empty}>{error}</p>}

        <div className={styles.categoryBar}>
          {CATEGORY_OPTIONS.map((opt) => (
            <button
              key={opt.value || "todos"}
              type="button"
              className={`${styles.categoryButton} ${category === opt.value ? styles.categoryButtonActive : ""}`}
              style={category === opt.value ? { background: opt.color, borderColor: opt.color } : undefined}
              onClick={() => setCategory(opt.value)}
            >
              <span className={styles.categoryDot} style={{ background: opt.color }} />
              {opt.label}
            </button>
          ))}
        </div>

        <div className={styles.periodBar}>
          <div className={styles.periodSegments}>
            {GRANULARITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`${styles.periodSegment} ${granularity === opt.value ? styles.periodSegmentActive : ""}`}
                onClick={() => setGranularity(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className={styles.periodNav}>
            <button
              type="button"
              className={styles.periodNavButton}
              onClick={() => setPeriodOffset((o) => o - 1)}
              aria-label="Período anterior"
            >
              <ChevronLeft size={16} />
            </button>
            <span className={styles.periodNavLabel}>{periodLabel(granularity, periodOffset)}</span>
            <button
              type="button"
              className={styles.periodNavButton}
              onClick={() => setPeriodOffset((o) => Math.min(0, o + 1))}
              disabled={isCurrentPeriod}
              aria-label="Período siguiente"
            >
              <ChevronRight size={16} />
            </button>
          </div>
          <div className={styles.ivaToggle} role="group" aria-label="Montos con o sin IVA">
            {(["bruto", "neto"] as IvaMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={ivaMode === mode}
                className={`${styles.ivaButton} ${ivaMode === mode ? styles.ivaButtonActive : ""}`}
                onClick={() => setIvaMode(mode)}
                title={mode === "bruto" ? "Montos tal como se pagaron, con IVA" : "Montos sin IVA (si la empresa lo recupera como crédito tributario)"}
              >
                {mode === "bruto" ? "Con IVA" : "Sin IVA"}
              </button>
            ))}
          </div>
        </div>
        <p className={styles.ivaNote}>
          Montos {ivaMode === "bruto" ? "tal como se pagaron (con IVA)" : "sin IVA (neto)"}.
          {costModel?.iva.estado === "pendiente_de_verificacion_contable" &&
            " Las tarifas de IVA son provisionales: pendientes de confirmar con el contador."}
        </p>

        <div className={styles.kpiRow}>
          <div className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <DollarSign size={16} className={styles.kpiIcon} />
              <span className={styles.kpiLabel}>{category ? `Gasto — ${activeOption.label}` : "Gasto operativo de la flota"}</span>
            </div>
            <div className={styles.kpiValue}>
              {isLoading ? "—" : currency.format(Number(summary?.fleet_total_cost ?? 0))}
            </div>
            <div className={styles.kpiContext}>
              {variationPct !== null ? (
                <span
                  className={`${styles.variationBadge} ${
                    variationPct > 0.5 ? styles.variationUp : variationPct < -0.5 ? styles.variationDown : styles.variationFlat
                  }`}
                >
                  {variationPct > 0.5 ? "▲" : variationPct < -0.5 ? "▼" : "="} {Math.abs(variationPct).toFixed(1)}%
                </span>
              ) : (
                <span>—</span>
              )}
              vs. período anterior
            </div>
            <p className={styles.kpiExplain}>
              Costos variables: combustible, peajes, alimentación y mantenimiento.{" "}
              {isCurrentPeriod ? "Se compara con los mismos días del período anterior." : "¿Gasto más o menos que en el período anterior?"}
            </p>
          </div>

          <div className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <TrendingUp size={16} className={styles.kpiIcon} />
              <span className={styles.kpiLabel}>{isCurrentPeriod ? "Proyección de cierre" : "Total del período"}</span>
            </div>
            <div className={styles.kpiValue}>{projectedClose !== null ? currency.format(projectedClose) : "—"}</div>
            <div className={styles.kpiContext}>
              {isCurrentPeriod ? "al ritmo actual" : "período cerrado"} · día {progress.elapsed} de {progress.total}
            </div>
            <p className={styles.kpiExplain}>
              {isCurrentPeriod ? "Si sigo gastando igual, ¿en cuánto cierro el período?" : "El gasto total de este período ya cerrado."}
              {isCurrentPeriod && (
                <>
                  {" "}
                  {projectedCloseRange
                    ? `Estimación lineal (heurística). Rango probable, según cuánto varió el gasto en períodos completos anteriores: ${currency.format(projectedCloseRange.low)} – ${currency.format(projectedCloseRange.high)}.`
                    : `Estimación lineal (heurística), no un pronóstico estadístico: asume ritmo de gasto uniforme, algo poco realista en la práctica.`}
                </>
              )}
            </p>
          </div>

          <div className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <Gauge size={16} className={styles.kpiIcon} />
              <span className={styles.kpiLabel}>{costPerKmLabel}</span>
            </div>
            <div className={styles.kpiValue}>{costPerKm !== null ? `${currency.format(costPerKm)}/km` : "—"}</div>
            <div className={styles.kpiContext}>
              {fleetDistanceKm.toLocaleString("es-EC")} km recorridos
              {!category && fixedIncluded && fleetCosts?.cv_per_km != null && fleetCosts?.cf_per_km != null
                ? ` · variable ${currency.format(Number(fleetCosts.cv_per_km))} + fijo ${currency.format(Number(fleetCosts.cf_per_km))}`
                : ""}
            </div>
            <p className={styles.kpiExplain}>
              {category || fixedIncluded
                ? "Eficiencia real de la flota, sin importar cuánto se use cada unidad."
                : "Solo costos variables: el costo fijo y de personal lo ve el administrador."}
            </p>
          </div>

          <div className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <AlertTriangle size={16} className={styles.kpiIcon} style={{ color: urgentAlerts.length > 0 ? "var(--danger)" : undefined }} />
              <span className={styles.kpiLabel}>Mantenimientos urgentes</span>
            </div>
            <div className={`${styles.kpiValue} ${urgentAlerts.length > 0 ? styles.kpiValueAlert : ""}`}>
              {isLoading ? "—" : urgentAlerts.length}
            </div>
            <div className={styles.kpiContext}>
              {overdueCount} vencido(s) · {dueSoonCount} próximo(s)
            </div>
            <p className={styles.kpiExplain}>Vehículos que necesitan taller pronto — el detalle está abajo.</p>
          </div>
        </div>

        <div className={styles.sectionHeader}>
          <DollarSign size={18} />
          <span className={styles.sectionLabel}>Rentabilidad y eficiencia</span>
        </div>

        <div className={styles.kpiRow}>
          <div className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <TrendingUp size={16} className={styles.kpiIcon} />
              <span className={styles.kpiLabel}>{fixedIncluded && fleetCosts?.profit != null ? "Utilidad del período" : "Margen de contribución"}</span>
            </div>
            <div className={styles.kpiValue}>
              {fixedIncluded && fleetCosts?.profit != null
                ? currency.format(Number(fleetCosts.profit))
                : fleetMargin !== null
                  ? currency.format(fleetMargin)
                  : "—"}
            </div>
            <div className={styles.kpiContext}>
              {fixedIncluded && fleetCosts?.margin_pct != null
                ? `${Number(fleetCosts.margin_pct).toFixed(1)}% del ingreso`
                : marginPct !== null
                  ? `${marginPct.toFixed(0)}% del ingreso`
                  : hasRevenueData
                    ? "—"
                    : "sin ingresos registrados"}
            </div>
            <p className={styles.kpiExplain}>
              {!hasRevenueData
                ? "Registra el ingreso al cerrar un viaje para ver el margen real, no solo el gasto."
                : fixedIncluded && fleetCosts?.profit != null
                  ? "Ingreso menos el costo total (variable, fijo y de personal): la utilidad que usa la literatura de transporte."
                  : "Ingreso menos costos variables. No incluye costos fijos ni de personal, así que es mayor que la utilidad real."}
              {revenueCoverage !== null && revenueCoverage < 100 &&
                ` Ojo: solo el ${revenueCoverage.toFixed(0)}% de los km tiene ingreso registrado; el resultado está subestimado.`}
            </p>
          </div>

          <div className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <Fuel size={16} className={styles.kpiIcon} />
              <span className={styles.kpiLabel}>Consumo de combustible</span>
            </div>
            <div className={styles.kpiValue}>{fleetFuelEfficiency !== null ? `${fleetFuelEfficiency.toFixed(1)} L/100km` : "—"}</div>
            <div className={styles.kpiContext}>{fleetFuelLiters > 0 ? `${fleetFuelLiters.toLocaleString("es-EC", { maximumFractionDigits: 0 })} litros cargados` : "sin litros registrados"}</div>
            <p className={styles.kpiExplain}>Distinto del costo: el precio del diésel sube y baja; el consumo delata fallas o mal manejo.</p>
          </div>

          <div className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <Activity size={16} className={styles.kpiIcon} />
              <span className={styles.kpiLabel}>Utilización de la flota</span>
            </div>
            <div className={styles.kpiValue}>{avgUtilization !== null ? `${avgUtilization.toFixed(0)}%` : "—"}</div>
            <div className={styles.kpiContext}>% de días del período con al menos un viaje</div>
            <p className={styles.kpiExplain}>
              Aproximación por actividad registrada — no es un registro real de tiempo en taller (ese evento no existe todavía en el sistema).
            </p>
          </div>
        </div>

        <div className={styles.sectionHeader}>
          <PieChart size={18} />
          <span className={styles.sectionLabel}>Estructura de costos — de dónde sale cada dólar por kilómetro</span>
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Costo del kilómetro en ocho categorías</span>
          </div>
          <p className={styles.panelSubtitle}>
            Costo total Ct = costos variables Cv + costos fijos Cf (Poliak et al., 2025), repartido en las ocho categorías del
            costo de un vehículo-km (Zysińska &amp; Menes, 2026).
          </p>

          {fleetCosts && !fixedIncluded && (
            <p className={styles.notice}>
              {summary?.fixed_costs_omitted_reason === "rol"
                ? "Los costos fijos y de personal solo los ve el administrador. Aquí se muestran los costos variables."
                : "Sin un período con fechas no se pueden prorratear los costos fijos. Aquí se muestran los costos variables."}
            </p>
          )}
          {noFixedCostsYet && (
            <p className={styles.notice}>
              Todavía no hay costos fijos ni de personal para este período, así que el costo total es solo el variable.{" "}
              <Link to="/costos">Registrarlos en Costos</Link>.
            </p>
          )}

          {fleetCosts ? (
            <>
              <div className={styles.costStats}>
                {(
                  [
                    ["Costo variable (Cv)", fleetCosts.variable_cost, false],
                    ["Costo fijo (Cf)", fleetCosts.fixed_cost, false],
                    ["Costo total (Ct)", fleetCosts.total_cost, false],
                    ["Ingreso", fleetCosts.revenue, false],
                    ["Utilidad", fleetCosts.profit, false],
                    ["Personal (PC)", fleetCosts.personnel_cost, false],
                  ] as const
                )
                  .filter(([, value]) => value !== null)
                  .map(([label, value]) => (
                    <div className={styles.costStat} key={label}>
                      <span className={styles.costStatLabel}>{label}</span>
                      <span className={styles.costStatValue}>{currency.format(Number(value))}</span>
                    </div>
                  ))}
                {fixedIncluded && fleetCosts.labour_productivity != null && (
                  <div className={styles.costStat}>
                    <span className={styles.costStatLabel}>Productividad laboral (ingreso ÷ personal)</span>
                    <span className={styles.costStatValue}>{Number(fleetCosts.labour_productivity).toFixed(2)}×</span>
                  </div>
                )}
                {fixedIncluded && fleetCosts.return_on_personnel_cost_pct != null && (
                  <div className={styles.costStat}>
                    <span className={styles.costStatLabel}>Retorno sobre costo de personal</span>
                    <span className={styles.costStatValue}>{Number(fleetCosts.return_on_personnel_cost_pct).toFixed(1)}%</span>
                  </div>
                )}
              </div>

              <div className={styles.compTable}>
                <div className={`${styles.compRow} ${styles.compHead}`}>
                  <span>Categoría</span>
                  <span />
                  <span className={styles.compNum}>Monto</span>
                  <span className={styles.compNum}>Por km</span>
                  <span className={styles.compNum}>% del {fixedIncluded ? "costo total" : "costo variable"}</span>
                </div>
                {fleetCosts.composition
                  .filter((c) => fixedIncluded || Number(c.amount) > 0)
                  .map((c) => (
                    <div className={styles.compRow} key={c.key}>
                      <span>{c.label}</span>
                      <span className={styles.compBarTrack}>
                        <span className={styles.compBarFill} style={{ width: `${Math.min(100, Number(c.share_pct ?? 0))}%` }} />
                      </span>
                      <span className={`${styles.compNum} mono`}>{currency.format(Number(c.amount))}</span>
                      <span className={`${styles.compNum} mono`}>{c.per_km != null ? currency.format(Number(c.per_km)) : "—"}</span>
                      <span className={`${styles.compNum} mono`}>{c.share_pct != null ? `${Number(c.share_pct).toFixed(1)}%` : "—"}</span>
                    </div>
                  ))}
              </div>
              {summary?.unallocated_personnel_cost && Number(summary.unallocated_personnel_cost) > 0 && (
                <p className={styles.compFootnote}>
                  Incluye {currency.format(Number(summary.unallocated_personnel_cost))} de personal de conductores sin kilómetros en el período:
                  cuenta en el total de la flota, en ningún vehículo.
                </p>
              )}
              {costModel && (
                <details className={styles.method}>
                  <summary>Cómo se calcula cada indicador</summary>
                  <ul>
                    {costModel.indicators.map((i) => (
                      <li key={i.id}>
                        <strong>{i.name}</strong>: {i.formula} — <em>{i.source}</em>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "Sin datos para este período."}</p>
          )}
        </div>

        <div className={styles.actionZone}>
          <div className={styles.sectionHeader}>
            <Wrench size={18} />
            <span className={styles.sectionLabel}>Acción requerida — qué hacer primero</span>
          </div>

          <div className={styles.chartsGrid}>
            <div className={styles.panel}>
              <div className={styles.panelHead}>
                <span className={styles.panelTitle}>Mantenimientos por atender</span>
              </div>
              <p className={styles.panelSubtitle}>Ordenados por urgencia: vencidos primero, luego los que se acercan al límite.</p>
              {urgentAlerts.length > 0 ? (
              urgentAlerts.map((a) => (
                <div className={styles.alertRow} key={`${a.vehicle_id}-${a.maintenance_type}`}>
                  <div className={styles.alertInfo}>
                    <span className={styles.alertVehicle}>{a.vehicle_plate}</span>
                    <span className={styles.alertDetail}>
                      {MAINT_TYPE_LABELS[a.maintenance_type] ?? a.maintenance_type}
                      {a.km_remaining !== null &&
                        (a.km_remaining <= 0
                          ? ` · ${Math.abs(a.km_remaining).toLocaleString("es-EC")} km excedidos`
                          : ` · faltan ${a.km_remaining.toLocaleString("es-EC")} km`)}
                    </span>
                  </div>
                  <span
                    className={`${styles.urgencyBadge} ${
                      a.urgency === "vencido" ? styles.urgencyVencido : styles.urgencyProximo
                    }`}
                  >
                    {a.urgency === "vencido" ? "Vencido" : "Próximo"}
                  </span>
                </div>
              ))
            ) : (
              <p className={styles.empty}>{isLoading ? "Cargando…" : proximoKm != null ? `Todo al día — ningún mantenimiento a menos de ${proximoKm.toLocaleString("es-EC")} km.` : "Todo al día — ningún mantenimiento próximo."}</p>
            )}
          </div>

          <div className={styles.panel}>
            <div className={styles.panelHead}>
              <span className={styles.panelTitle}>Prioridad de atención</span>
            </div>
            <p className={styles.panelSubtitle}>Combina el costo del vehículo con la urgencia de su mantenimiento — la barra más larga es lo primero que hay que revisar.</p>
            <div className={styles.ahpControl}>
              <label htmlFor="ahp-select">¿Qué pesa más al decidir qué reparar primero: la urgencia o el costo?</label>
              <select
                id="ahp-select"
                value={urgencyOverCost}
                onChange={(e) => setUrgencyOverCost(Number(e.target.value))}
              >
                {SAATY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <span className={styles.ahpWeights}>
                {attention
                  ? `Con esta elección: urgencia ${(attention.weights.urgencia * 100).toFixed(0)}% · costo ${(attention.weights.costo * 100).toFixed(0)}% del criterio`
                  : "Calculando pesos…"}
              </span>
            </div>
            {priorityRanking.length > 0 ? (
              priorityRanking.map((v, idx) => (
                <div className={styles.priorityItem} key={v.vehicle_id}>
                  <span className={styles.priorityRank}>#{idx + 1}</span>
                  <div className={styles.priorityBody}>
                    <div className={styles.priorityHead}>
                      <span className={styles.priorityPlate}>{v.vehicle_plate}</span>
                      <span>{currency.format(Number(v.total_cost))}</span>
                    </div>
                    <div className={styles.priorityBarTrack}>
                      <div
                        className={styles.priorityBarFill}
                        style={{
                          width: `${Math.round(v.attention_score * 100)}%`,
                          background: v.worst_urgency === "vencido" ? "var(--danger)" : v.worst_urgency === "proximo" ? "var(--warning)" : "var(--brand-accent)",
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className={styles.empty}>{isLoading ? "Cargando…" : "Sin vehículos que requieran atención prioritaria."}</p>
            )}
          </div>
        </div>

          <div className={styles.panel}>
            <div className={styles.panelHead}>
              <span className={styles.panelTitle}>Mantenimiento preventivo vs. correctivo</span>
            </div>
            <p className={styles.panelSubtitle}>
              Mucho correctivo (rojo) frente a preventivo (verde) es señal de que se repara sobre la marcha en vez de
              planificar.
            </p>
            {maintenanceStatus && maintenanceStatus.mix.length > 0 ? (
              <PlotFigure
                height={190}
                deps={[maintenanceStatus.mix]}
                render={(width) => buildMaintenanceMixPlot(maintenanceStatus.mix, width)}
              />
            ) : (
              <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay mantenimientos completados para comparar."}</p>
            )}
          </div>
        </div>

        <div className={styles.sectionHeader} style={{ marginTop: "0.5rem" }}>
          <PieChart size={18} />
          <span className={styles.sectionLabel}>Análisis de costos — por qué está pasando</span>
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>
              {category ? `Gasto en ${activeOption.label.toLowerCase()} por vehículo` : "Composición de gastos por vehículo"}
            </span>
            {isAdmin && (
              <button type="button" className={styles.exportButton} onClick={handleExport}>
                Exportar a Excel
              </button>
            )}
          </div>

          <p className={styles.panelSubtitle}>
            {category ? "¿Qué vehículo concentra este tipo de gasto?" : "¿En qué se está yendo el dinero, vehículo por vehículo?"}
          </p>

          {!category && fleetTotal > 0 && (
            <div className={styles.percentRow}>
              <span className={styles.percentHint}>% del gasto operativo:</span>
              {(
                [
                  ["combustible", "Combustible", "var(--chart-combustible)"],
                  ["peaje", "Peajes", "var(--chart-peaje)"],
                  ["alimentacion", "Alimentación", "var(--chart-alimentacion)"],
                  ["mantenimiento", "Mantenimiento", "var(--chart-mantenimiento)"],
                ] as const
              ).map(([key, label, color]) => (
                <span className={styles.percentChip} key={key}>
                  <span className={styles.percentDot} style={{ background: color }} />
                  {label} {((categoryTotals[key] / fleetTotal) * 100).toFixed(0)}%
                </span>
              ))}
            </div>
          )}

          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData} margin={{ top: 24, right: 8, left: 0, bottom: 0 }} barCategoryGap="28%">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="placa" tick={axisStyle} tickLine={{ stroke: "var(--ink)" }} axisLine={{ stroke: "var(--ink)" }} />
                <YAxis
                  tick={axisStyle}
                  tickLine={{ stroke: "var(--ink)" }}
                  axisLine={{ stroke: "var(--ink)" }}
                  width={64}
                  tickFormatter={(value: number) => currencyCompact.format(value)}
                >
                  <Label
                    value="Costo (USD)"
                    angle={-90}
                    position="insideLeft"
                    style={{ fontSize: 11, fill: "var(--ink)", textAnchor: "middle" }}
                  />
                </YAxis>
                <Tooltip
                  formatter={(value: number) => currency.format(value)}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid var(--line)",
                    boxShadow: "var(--shadow-card)",
                    fontSize: 13,
                  }}
                />
                {category ? (
                  <Bar dataKey="seleccionado" name={activeOption.label} maxBarSize={72} stroke="var(--ink)" strokeWidth={1}>
                    {chartData.map((entry) => (
                      <Cell key={entry.placa} fill={activeOption.color} />
                    ))}
                    <LabelList
                      dataKey="seleccionado"
                      position="insideTop"
                      formatter={(value: number) => currencyCompact.format(value)}
                      style={{ fill: "#fff", fontWeight: 700, fontSize: 12 }}
                    />
                  </Bar>
                ) : (
                  <>
                    <Legend
                      wrapperStyle={{
                        fontSize: 12,
                        border: "1px solid var(--ink)",
                        padding: "0.3rem 0.65rem",
                        background: "var(--surface)",
                      }}
                    />
                    <Bar dataKey="Combustible" stackId="gastos" fill="var(--chart-combustible)" stroke="var(--ink)" strokeWidth={1} />
                    <Bar dataKey="Peajes" stackId="gastos" fill="var(--chart-peaje)" stroke="var(--ink)" strokeWidth={1} />
                    <Bar dataKey="Alimentación" stackId="gastos" fill="var(--chart-alimentacion)" stroke="var(--ink)" strokeWidth={1} />
                    <Bar dataKey="Mantenimiento" stackId="gastos" fill="var(--chart-mantenimiento)" stroke="var(--ink)" strokeWidth={1} />
                  </>
                )}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className={styles.empty}>
              {isLoading ? "Cargando…" : "Todavía no hay viajes completados para calcular costos."}
            </p>
          )}
        </div>

        <div className={styles.chartsGrid}>
          <div className={styles.panel}>
            <div className={styles.panelHead}>
              <span className={styles.panelTitle}>
                Distribución de montos — {activeOption.label.toLowerCase()}
              </span>
            </div>
            <p className={styles.panelSubtitle}>¿Hay algún gasto individual fuera de lo normal que valga la pena revisar?</p>
            {records.length > 0 ? (
              <PlotFigure
                height={240}
                deps={[records, activeOption.value]}
                render={(width) => buildHistogramPlot(records, width, activeOption.color)}
              />
            ) : (
              <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay registros para esta categoría."}</p>
            )}
          </div>

          <div className={styles.panel}>
            <div className={styles.panelHead}>
              <span className={styles.panelTitle}>
                Kilometraje vs. monto — {activeOption.label.toLowerCase()}
              </span>
            </div>
            <p className={styles.panelSubtitle}>¿El gasto crece con el uso real, o hay unidades que cuestan más de lo que deberían?</p>
            {records.some((r) => r.mileage_km != null) ? (
              <PlotFigure
                height={240}
                deps={[records, activeOption.value]}
                render={(width) => buildScatterPlot(records, width)}
              />
            ) : (
              <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay registros con kilometraje asociado."}</p>
            )}
          </div>
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>
              Tendencia por {granularity === "year" ? "año" : granularity === "month" ? "mes" : "semana"} — {activeOption.label.toLowerCase()}
            </span>
          </div>
          <p className={styles.panelSubtitle}>
            Todo el historial disponible hasta {periodLabel(granularity, periodOffset).toLowerCase()} — ¿el gasto sube o baja?
          </p>
          {trendPoints.length > 0 ? (
            <PlotFigure
              height={trendPlotHeight(trendPoints)}
              deps={[trendPoints, activeOption.value]}
              render={(width) => buildTrendPlot(trendPoints, width, activeOption.color)}
            />
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay costos para graficar la tendencia."}</p>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Vehículos — todos los parámetros de gasto</span>
          </div>
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Placa</th>
                  <th>Marca / modelo</th>
                  <th>Km actual</th>
                  <th>Viajes</th>
                  <th>Combustible</th>
                  <th>Peajes</th>
                  <th>Alimentación</th>
                  <th>Mantenimiento</th>
                  <th>{category ? `Gasto (${activeOption.label})` : "Gasto operativo"}</th>
                  <th>Gasto/km</th>
                  <th>Consumo</th>
                  <th>Contribución</th>
                  {fixedIncluded && (
                    <>
                      <th>Costo total (Ct)</th>
                      <th>Ct/km</th>
                      <th>Utilidad</th>
                    </>
                  )}
                  <th>Utilización</th>
                  <th>Alertas</th>
                </tr>
              </thead>
              <tbody>
                {summary?.vehicles.map((v) => (
                  <tr key={v.vehicle_id}>
                    <td className="mono">{v.plate}</td>
                    <td>
                      {v.brand} {v.model}
                    </td>
                    <td className="mono">{v.current_mileage_km.toLocaleString("es-EC")}</td>
                    <td className="mono">{v.trip_count}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.combustible))}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.peaje))}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.alimentacion))}</td>
                    <td className="mono">{currency.format(Number(v.breakdown.mantenimiento))}</td>
                    <td className="mono">{currency.format(Number(v.total_cost))}</td>
                    <td className="mono">
                      {v.distance_km > 0 ? `${currency.format(Number(v.total_cost) / v.distance_km)}/km` : "—"}
                    </td>
                    <td className="mono">
                      {v.fuel_efficiency_l_100km !== null ? `${Number(v.fuel_efficiency_l_100km).toFixed(1)} L/100km` : "—"}
                    </td>
                    <td className="mono">{v.margin !== null ? currency.format(Number(v.margin)) : "—"}</td>
                    {fixedIncluded && (
                      <>
                        <td className="mono">{v.costs?.total_cost != null ? currency.format(Number(v.costs.total_cost)) : "—"}</td>
                        <td className="mono">{v.costs?.ct_per_km != null ? `${currency.format(Number(v.costs.ct_per_km))}/km` : "—"}</td>
                        <td className="mono">{v.costs?.profit != null ? currency.format(Number(v.costs.profit)) : "—"}</td>
                      </>
                    )}
                    <td className="mono">{v.utilization_pct !== null ? `${Number(v.utilization_pct).toFixed(0)}%` : "—"}</td>
                    <td>
                      {v.pending_maintenance_alerts > 0 ? (
                        <span className={styles.badge}>{v.pending_maintenance_alerts} pendiente(s)</span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!isLoading && summary?.vehicles.length === 0 && (
            <p className={styles.empty}>Todavía no hay vehículos registrados.</p>
          )}
        </div>

        <div className={styles.sectionHeader}>
          <Users size={18} />
          <span className={styles.sectionLabel}>Análisis por conductor — quién genera el gasto</span>
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Conductores — costo operativo y eficiencia</span>
          </div>
          <p className={styles.panelSubtitle}>
            Combustible, peajes y alimentación por conductor — el mantenimiento no se incluye porque depende del
            vehículo, no de quién lo conducía. El costo/km no controla por dificultad de ruta: revisa el panel de
            "Costo por ruta" de al lado antes de comparar conductores entre sí.
            {category === "mantenimiento" && " (mostrando el total sin filtrar, ya que este filtro no aplica aquí)"}
          </p>
          {driverSummary && driverSummary.drivers.some((d) => d.trip_count > 0) ? (
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Conductor</th>
                    <th>Viajes</th>
                    <th>Km conducidos</th>
                    <th>Combustible</th>
                    <th>Peajes</th>
                    <th>Alimentación</th>
                    <th>Total</th>
                    <th>Costo/km</th>
                    <th>Consumo</th>
                    <th>Contribución</th>
                    {driverSummary.personnel_included && (
                      <>
                        <th>Personal</th>
                        <th>Ingreso por $ de personal</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {[...driverSummary.drivers]
                    .filter((d) => d.trip_count > 0)
                    .sort((a, b) => Number(b.total_cost) - Number(a.total_cost))
                    .map((d) => (
                      <tr key={d.driver_id}>
                        <td>{d.full_name}</td>
                        <td className="mono">{d.trip_count}</td>
                        <td className="mono">{d.distance_km.toLocaleString("es-EC")}</td>
                        <td className="mono">{currency.format(Number(d.breakdown.combustible))}</td>
                        <td className="mono">{currency.format(Number(d.breakdown.peaje))}</td>
                        <td className="mono">{currency.format(Number(d.breakdown.alimentacion))}</td>
                        <td className="mono">{currency.format(Number(d.total_cost))}</td>
                        <td className="mono">{d.cost_per_km !== null ? `${currency.format(Number(d.cost_per_km))}/km` : "—"}</td>
                        <td className="mono">{d.fuel_efficiency_l_100km !== null ? `${Number(d.fuel_efficiency_l_100km).toFixed(1)} L/100km` : "—"}</td>
                        <td className="mono">{d.margin !== null ? currency.format(Number(d.margin)) : "—"}</td>
                        {driverSummary.personnel_included && (
                          <>
                            <td className="mono">{d.personnel_cost != null ? currency.format(Number(d.personnel_cost)) : "—"}</td>
                            <td className="mono">{d.labour_productivity != null ? `${Number(d.labour_productivity).toFixed(2)}×` : "—"}</td>
                          </>
                        )}
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay viajes de conductores en este período."}</p>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>
              <MapPin size={16} style={{ display: "inline", verticalAlign: "-3px", marginRight: "0.4rem" }} />
              Costo por ruta
            </span>
          </div>
          <p className={styles.panelSubtitle}>
            El contexto que falta arriba: un conductor caro puede ser mal manejo, o puede ser que le tocaron las
            rutas más costosas. Compara su costo/km contra el de la ruta, no solo contra otros conductores.
          </p>
          {routeSummary && routeSummary.routes.length > 0 ? (
            <PlotFigure
              height={220}
              deps={[routeSummary.routes]}
              render={(width) => buildRouteCostPlot(routeSummary.routes, width)}
            />
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay rutas con costos en este período."}</p>
          )}
        </div>

        <div>
          <div className={styles.panelTitle} style={{ marginBottom: "0.85rem" }}>
            Módulos del sistema
          </div>
          <div className={styles.actionsGrid}>
            {NAV_ITEMS.filter((item) => !item.adminOnly || user?.role.name === "admin").map((item) => (
              <Link key={item.path} to={item.path} className={styles.actionCard}>
                <item.icon size={20} strokeWidth={2} color="var(--brand-navy)" />
                <div className={styles.actionLabel}>{item.label}</div>
                <div className={styles.actionDesc}>{item.description}</div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default DashboardPage;
