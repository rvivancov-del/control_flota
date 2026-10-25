// Llamadas HTTP a reporting-service (vía el gateway): dashboard, tendencias
// y reportes exportables.
import { apiClient } from "./apiClient";
import type { DashboardSummary } from "../types/dashboard";
import type {
  CostModelInfo,
  DriverSummaryResponse,
  ExpenseRecord,
  MaintenancePriorityResponse,
  MaintenanceReportItem,
  MaintenanceStatus,
  ReportFilters,
  RouteSummaryResponse,
  TrendResponse,
  VehicleAttentionResponse,
} from "../types/reports";

// Mismo criterio que apiClient.ts: usar el host real de la página, no un
// "localhost" fijo que se rompe al abrir el panel desde otro dispositivo
// en la red local.
const BASE_URL = () =>
  import.meta.env.VITE_API_BASE_URL ?? `http://${window.location.hostname}:8080/api`;

function buildParams(filters: ReportFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.vehicle_id) params.set("vehicle_id", filters.vehicle_id);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.category) params.set("category", filters.category);
  if (filters.iva_mode) params.set("iva_mode", filters.iva_mode);
  return params;
}

function queryString(filters: ReportFilters): string {
  const qs = buildParams(filters).toString();
  return qs ? `?${qs}` : "";
}

export const reportsApi = {
  summary: (token: string, filters: ReportFilters = {}) =>
    apiClient.get<DashboardSummary>(`/reports/dashboard/summary${queryString(filters)}`, token),

  trend: (token: string, period: "week" | "month" | "year", filters: ReportFilters = {}) => {
    const params = buildParams(filters);
    params.set("period", period);
    return apiClient.get<TrendResponse>(`/reports/dashboard/trend?${params.toString()}`, token);
  },

  maintenanceReport: (token: string, filters: ReportFilters = {}) =>
    apiClient.get<MaintenanceReportItem[]>(`/reports/reports/maintenance${queryString(filters)}`, token),

  records: (token: string, filters: ReportFilters = {}) =>
    apiClient.get<ExpenseRecord[]>(`/reports/dashboard/records${queryString(filters)}`, token),

  maintenanceStatus: (token: string, filters: ReportFilters = {}) =>
    apiClient.get<MaintenanceStatus>(`/reports/dashboard/maintenance-status${queryString(filters)}`, token),

  maintenancePriority: (token: string, filters: ReportFilters = {}) =>
    apiClient.get<MaintenancePriorityResponse>(`/reports/dashboard/maintenance-priority${queryString(filters)}`, token),

  /** RF-19: ranking de atención por vehículo; los pesos salen de la razón de Saaty elegida. */
  vehicleAttention: (token: string, urgencyOverCost: number, filters: ReportFilters = {}) => {
    const params = buildParams(filters);
    params.set("urgency_over_cost", String(urgencyOverCost));
    return apiClient.get<VehicleAttentionResponse>(`/reports/dashboard/vehicle-attention?${params.toString()}`, token);
  },

  drivers: (token: string, filters: ReportFilters = {}) =>
    apiClient.get<DriverSummaryResponse>(`/reports/dashboard/drivers${queryString(filters)}`, token),

  routes: (token: string, filters: ReportFilters = {}) =>
    apiClient.get<RouteSummaryResponse>(`/reports/dashboard/routes${queryString(filters)}`, token),

  /** Metodología del modelo de costos: categorías, fórmulas, fuentes y tarifas de IVA con su estado. */
  costModel: (token: string) => apiClient.get<CostModelInfo>("/reports/dashboard/cost-model", token),

  exportUrl: (filters: ReportFilters = {}) => `${BASE_URL()}/reports/reports/costs.xlsx${queryString(filters)}`,
  exportPdfUrl: (filters: ReportFilters = {}) => `${BASE_URL()}/reports/reports/costs.pdf${queryString(filters)}`,
};
