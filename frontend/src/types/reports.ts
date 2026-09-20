// Tipos de tendencias, reportes, conductores/rutas y priorización AHP
// (RF-20), reflejo de los esquemas de reporting-service.
import type { ExpenseBreakdown } from "./dashboard";

export type TrendPoint = {
  period_label: string;
  total_cost: string;
  breakdown: ExpenseBreakdown;
};

export type TrendResponse = {
  points: TrendPoint[];
};

export type MaintenanceReportItem = {
  vehicle_plate: string;
  maintenance_type: string;
  category: string;
  status: string;
  scheduled_mileage_km: number | null;
  performed_mileage_km: number | null;
  cost: string | null;
  performed_at: string | null;
};

export type ExpenseCategory = "combustible" | "peaje" | "alimentacion" | "mantenimiento";

export type ExpenseRecord = {
  vehicle_plate: string;
  category: string;
  amount: string;
  mileage_km: number | null;
  occurred_at: string | null;
};

export type MaintenanceUrgency = "vencido" | "proximo" | "normal";

export type MaintenanceAlertDetail = {
  vehicle_id: string;
  vehicle_plate: string;
  maintenance_type: string;
  category: string;
  scheduled_mileage_km: number | null;
  current_mileage_km: number;
  km_remaining: number | null;
  urgency: MaintenanceUrgency;
};

export type MaintenanceMixEntry = {
  category: string;
  count: number;
  total_cost: string;
};

export type MaintenanceStatus = {
  alerts: MaintenanceAlertDetail[];
  mix: MaintenanceMixEntry[];
};

export type MaintenancePriorityItem = {
  vehicle_id: string;
  vehicle_plate: string;
  maintenance_type: string;
  category: string;
  km_remaining: number | null;
  seguridad_score: number;
  urgencia_score: number;
  costo_score: number;
  priority_score: number;
};

export type AhpCriteriaWeights = {
  seguridad: number;
  urgencia: number;
  costo: number;
  consistency_ratio: number;
  is_consistent: boolean;
};

export type MaintenancePriorityResponse = {
  items: MaintenancePriorityItem[];
  weights: AhpCriteriaWeights;
};

export type ReportFilters = {
  vehicle_id?: string;
  date_from?: string;
  date_to?: string;
  category?: ExpenseCategory;
};

export type DriverExpenseBreakdown = {
  combustible: string;
  peaje: string;
  alimentacion: string;
};

export type DriverSummary = {
  driver_id: string;
  full_name: string;
  trip_count: number;
  distance_km: number;
  total_cost: string;
  cost_per_km: string | null;
  breakdown: DriverExpenseBreakdown;
  revenue: string | null;
  margin: string | null;
  fuel_liters: string;
  fuel_efficiency_l_100km: string | null;
};

export type DriverSummaryResponse = {
  drivers: DriverSummary[];
  fleet_total_cost: string;
};

export type RouteSummary = {
  origin: string;
  destination: string;
  trip_count: number;
  avg_distance_km: number;
  cost_total: string;
  cost_per_km: string | null;
};

export type RouteSummaryResponse = {
  routes: RouteSummary[];
};
