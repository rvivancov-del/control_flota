// Tipos del portal de despacho por QR (RF-18), reflejo de fleet-core-service.
export type DespachoInfo = {
  driver_id: string;
  driver_name: string;
  driver_status: string;
  vehicle_id: string;
  vehicle_plate: string;
  vehicle_brand: string;
  vehicle_model: string;
  vehicle_registration_number: string | null;
  vehicle_current_mileage_km: number;
};

export type DespachoInput = {
  origin: string;
  destination: string;
  departure_at?: string;
  start_mileage_km: number;
  remission_guide?: string;
  cargo_type?: string;
  notes?: string;
  fuel_amount?: number;
  fuel_liters?: number;
};

export type DespachoResult = {
  trip: {
    id: string;
    origin: string;
    destination: string;
    departure_at: string;
    status: string;
  };
  message: string;
};
