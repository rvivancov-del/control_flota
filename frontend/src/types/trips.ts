// Tipos de viajes y gastos, reflejo de los esquemas de fleet-core-service.
export type TripStatus = "planificado" | "en_curso" | "completado" | "anulado" | string;

export type Trip = {
  id: string;
  vehicle_id: string;
  driver_id: string;
  created_by: string | null;
  origin: string;
  destination: string;
  departure_at: string;
  arrival_at: string | null;
  start_mileage_km: number;
  end_mileage_km: number | null;
  revenue: string | null;
  status: TripStatus;
  remission_guide: string | null;
  cargo_type: string | null;
  notes: string | null;
  created_at: string | null;
  km_recorridos: number | null;
};

export type TripInput = {
  vehicle_id: string;
  driver_id: string;
  origin: string;
  destination: string;
  departure_at: string;
  start_mileage_km: number;
};

export type TripCloseInput = {
  end_mileage_km: number;
  arrival_at: string;
  revenue?: number;
};

export type MaintenanceAlertBrief = {
  id: string;
  vehicle_id: string;
  maintenance_type: string;
  category: string;
  scheduled_mileage_km: number | null;
  km_remaining?: number | null;
  urgency?: "vencido" | "proximo" | null;
};

export type TripCloseResult = {
  trip: Trip;
  maintenance_alerts: MaintenanceAlertBrief[];
};

export type ExpenseType = "combustible" | "peaje" | "alimentacion";

export type Expense = {
  id: string;
  trip_id: string;
  type: ExpenseType;
  amount: string;
  liters: string | null;
  currency: string;
  expense_date: string;
  notes: string | null;
  receipt_url: string | null;
  created_at: string | null;
};

export type ExpenseInput = {
  type: ExpenseType;
  amount: number;
  liters?: number;
  currency: string;
  expense_date: string;
  notes?: string;
};
