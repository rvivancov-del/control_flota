// Tipos de vehículos y conductores, reflejo de los esquemas de fleet-core-service.
export type Vehicle = {
  id: string;
  plate: string;
  brand: string;
  model: string;
  year: number;
  current_mileage_km: number;
  status: "activo" | "mantenimiento" | "inactivo" | string;
  registration_number: string | null;
  created_at: string | null;
};

export type VehicleInput = {
  plate: string;
  brand: string;
  model: string;
  year: number;
  current_mileage_km: number;
  status: string;
  registration_number?: string;
};

export type Driver = {
  id: string;
  full_name: string;
  license_number: string;
  license_type: string | null;
  phone: string | null;
  status: "activo" | "inactivo" | string;
  assigned_vehicle_id: string | null;
  qr_token: string | null;
  created_at: string | null;
};

export type DriverInput = {
  full_name: string;
  license_number: string;
  license_type: string;
  phone: string;
  assigned_vehicle_id?: string;
};
