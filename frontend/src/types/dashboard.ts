// Tipos del resumen del dashboard, reflejo de los esquemas de reporting-service.
export type ExpenseBreakdown = {
  combustible: string;
  peaje: string;
  alimentacion: string;
  mantenimiento: string;
};

/** Fase 3: 'bruto' = montos pagados (con IVA); 'neto' = sin IVA. */
export type IvaMode = "bruto" | "neto";

/** Una de las ocho categorías del costo por kilómetro de Zysińska & Menes (2026). */
export type CostCategoryLine = {
  key: string;
  label: string;
  amount: string;
  per_km: string | null;
  share_pct: string | null;
};

/** Costos e indicadores de un vehículo o de la flota (Poliak et al., 2025; Zysińska & Menes, 2026; Kutac et al., 2022).
 * Los campos que dependen de los costos fijos y de personal son null cuando no se incluyen (rol operador o sin período). */
export type CostStructure = {
  iva_mode: IvaMode;
  fixed_included: boolean;
  distance_km: number;
  variable_cost: string; // Cv
  fixed_cost: string | null; // Cf
  total_cost: string | null; // Ct = Cv + Cf
  cv_per_km: string | null;
  cf_per_km: string | null;
  ct_per_km: string | null;
  revenue: string | null;
  revenue_per_km: string | null;
  /** % de los km con ingreso registrado: por debajo de 100 el margen se subestima. */
  revenue_coverage_pct: string | null;
  profit: string | null; // R − Ct
  profit_per_km: string | null;
  margin_pct: string | null;
  contribution_margin: string | null; // R − Cv
  personnel_cost: string | null;
  labour_productivity: string | null; // R / PC
  return_on_personnel_cost_pct: string | null; // (R − Ct) / PC × 100
  composition: CostCategoryLine[];
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
  costs: CostStructure | null;
};

/** `fleet_total_cost` y el `total_cost` de cada vehículo son el gasto operativo (costos variables), acotado por la
 * categoría elegida; `fleet_total_margin` es el margen de contribución y NO depende de la categoría. El costo total
 * y la utilidad completos están en `fleet_costs`. */
export type DashboardSummary = {
  vehicles: VehicleSummary[];
  fleet_total_cost: string;
  fleet_total_revenue: string | null;
  fleet_total_margin: string | null;
  iva_mode: IvaMode;
  fleet_costs: CostStructure | null;
  /** null = incluye costos fijos y de personal; "rol" = el rol no los ve; "sin_periodo" = falta el período. */
  fixed_costs_omitted_reason: "rol" | "sin_periodo" | null;
  unallocated_personnel_cost: string | null;
};
