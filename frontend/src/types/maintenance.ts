// Tipos de mantenimiento, reflejo de los esquemas de fleet-core-service.
export type MaintenanceType = "aceite" | "filtros" | "llantas" | "frenos" | "bocines" | "otro";
export type MaintenanceCategory = "preventivo" | "correctivo" | "programado_km";
export type MaintenanceStatus = "pendiente" | "en_proceso" | "completado" | string;

export type MaintenanceRecord = {
  id: string;
  vehicle_id: string;
  maintenance_type: MaintenanceType | string;
  category: MaintenanceCategory | string;
  scheduled_mileage_km: number | null;
  performed_mileage_km: number | null;
  cost: string | null;
  performed_at: string | null;
  status: MaintenanceStatus;
  created_at: string | null;
  /** RF-13: solo en mantenimientos pendientes; los calcula fleet-core-service. */
  km_remaining?: number | null;
  urgency?: "vencido" | "proximo" | "normal" | null;
};

/** RF-13: política de alertas vigente y su procedencia (GET /fleet/maintenance/policy). */
export type MaintenancePolicy = {
  version: string;
  estado: string;
  procedencia: string;
  proximo_km: number;
  proximo_km_por_tipo: Record<string, number>;
};

export type MaintenanceInput = {
  maintenance_type: string;
  category: string;
  scheduled_mileage_km: number | null;
};

export type MaintenanceCompleteInput = {
  performed_mileage_km: number;
  performed_at: string;
  cost: number;
};
