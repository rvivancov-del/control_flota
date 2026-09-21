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
  /** RF-18: el token del QR no se devuelve al listar (solo se guarda su hash); solo se informa el estado de la credencial. */
  has_qr: boolean;
  qr_token_expires_at: string | null;
  qr_token_last_used_at: string | null;
  /** RNF-11: no nulo cuando los datos personales fueron suprimidos (irreversible). */
  anonymized_at: string | null;
  created_at: string | null;
};

/** RF-05: tipo de licencia vigente en Ecuador (ANT) que acepta el sistema. */
export type LicenseType = { code: string; description: string };

/** Respuesta al emitir o rotar la credencial: el único momento en que el token viaja en claro. */
export type DriverQrIssued = Driver & { qr_token: string };

export type DriverInput = {
  full_name: string;
  license_number: string;
  license_type: string;
  phone: string;
  /** null desasigna el vehículo; undefined lo deja como está (edición) o sin asignar (alta). */
  assigned_vehicle_id?: string | null;
};
