// Costos fijos por vehículo y costos de personal por conductor (modelo de costos), reflejo de fleet-core-service.
export type FixedCostCategory = "depreciacion" | "capital" | "seguro" | "impuestos" | "otros";
export type CostPeriod = "mensual" | "anual";
export type PersonnelConcept = "sueldo" | "beneficios_sociales" | "otros";

export type FixedCost = {
  id: string;
  vehicle_id: string;
  category: FixedCostCategory;
  amount: string;
  period: CostPeriod;
  valid_from: string;
  valid_to: string | null;
  notes: string | null;
  created_at: string | null;
};

export type FixedCostInput = {
  vehicle_id: string;
  category: FixedCostCategory;
  amount: number;
  period: CostPeriod;
  valid_from: string;
  valid_to?: string | null;
  notes?: string;
};

export type PersonnelCost = {
  id: string;
  driver_id: string;
  concept: PersonnelConcept;
  amount: string; // monto mensual
  valid_from: string;
  valid_to: string | null;
  notes: string | null;
  created_at: string | null;
};

export type PersonnelCostInput = {
  driver_id: string;
  concept: PersonnelConcept;
  amount: number;
  valid_from: string;
  valid_to?: string | null;
  notes?: string;
};

export const FIXED_COST_LABELS: Record<FixedCostCategory, string> = {
  depreciacion: "Depreciación",
  capital: "Costo de capital (leasing, crédito)",
  seguro: "Seguro del vehículo",
  impuestos: "Impuestos y matrícula",
  otros: "Otros costos fijos",
};

export const PERSONNEL_LABELS: Record<PersonnelConcept, string> = {
  sueldo: "Sueldo",
  beneficios_sociales: "Beneficios sociales",
  otros: "Otros",
};
