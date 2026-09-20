// Tipos del resumen del dashboard, reflejo de los esquemas de reporting-service.
export type ExpenseBreakdown = {
  combustible: string;
  peaje: string;
  alimentacion: string;
  mantenimiento: string;
};

export type VehicleSummary = {
  vehicle_id: string;
  plate: string;
  brand: string;
  model: string;
  current_mileage_km: number;
  trip_count: number;
  distance_km: number;
  total_cost: string;
  breakdown: ExpenseBreakdown;
  pending_maintenance_alerts: number;
  revenue: string | null;
  margin: string | null;
  fuel_liters: string;
  fuel_efficiency_l_100km: string | null;
  active_days: number | null;
  period_days: number | null;
  utilization_pct: string | null;
};

export type DashboardSummary = {
  vehicles: VehicleSummary[];
  fleet_total_cost: string;
  fleet_total_revenue: string | null;
  fleet_total_margin: string | null;
};
