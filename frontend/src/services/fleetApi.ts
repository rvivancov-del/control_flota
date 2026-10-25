// Llamadas HTTP a fleet-core-service (vía el gateway): vehículos,
// conductores, viajes, gastos y mantenimiento.
import { apiClient } from "./apiClient";
import type { Driver, DriverInput, DriverQrIssued, LicenseType, Vehicle, VehicleInput } from "../types/fleet";
import type {
  Expense,
  ExpenseFilters,
  ExpenseInput,
  ExpenseRow,
  Trip,
  TripCloseInput,
  TripCloseResult,
  TripFilters,
  TripInput,
} from "../types/trips";
import type { FixedCost, FixedCostInput, PersonnelCost, PersonnelCostInput } from "../types/costs";
import type {
  MaintenanceCompleteInput,
  MaintenanceInput,
  MaintenancePolicy,
  MaintenanceRecord,
} from "../types/maintenance";

/** Arma ?a=1&b=2 omitiendo los filtros vacíos. */
function queryString(filters: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const fleetApi = {
  listVehicles: (token: string) => apiClient.get<Vehicle[]>("/fleet/vehicles", token),
  createVehicle: (token: string, payload: VehicleInput) =>
    apiClient.post<Vehicle>("/fleet/vehicles", payload, token),
  updateVehicle: (token: string, id: string, payload: Partial<VehicleInput>) =>
    apiClient.patch<Vehicle>(`/fleet/vehicles/${id}`, payload, token),

  listDrivers: (token: string) => apiClient.get<Driver[]>("/fleet/drivers", token),
  createDriver: (token: string, payload: DriverInput) =>
    apiClient.post<DriverQrIssued>("/fleet/drivers", payload, token),
  updateDriver: (token: string, id: string, payload: Partial<DriverInput> & { status?: string }) =>
    apiClient.patch<Driver>(`/fleet/drivers/${id}`, payload, token),
  listLicenseTypes: (token: string) => apiClient.get<LicenseType[]>("/fleet/drivers/license-types", token),
  /** RNF-11 (LOPDP): suprime los datos personales del conductor; es irreversible. */
  anonymizeDriver: (token: string, id: string) =>
    apiClient.post<Driver>(`/fleet/drivers/${id}/anonymize`, {}, token),
  regenerateDriverQr: (token: string, id: string) =>
    apiClient.post<DriverQrIssued>(`/fleet/drivers/${id}/regenerate-qr`, {}, token),
  revokeDriverQr: (token: string, id: string) =>
    apiClient.post<Driver>(`/fleet/drivers/${id}/revoke-qr`, {}, token),

  listTrips: (token: string, filters: TripFilters = {}) =>
    apiClient.get<Trip[]>(`/fleet/trips${queryString({ ...filters })}`, token),
  getTrip: (token: string, id: string) => apiClient.get<Trip>(`/fleet/trips/${id}`, token),
  createTrip: (token: string, payload: TripInput) =>
    apiClient.post<Trip>("/fleet/trips", payload, token),
  startTrip: (token: string, id: string) =>
    apiClient.patch<Trip>(`/fleet/trips/${id}/start`, {}, token),
  cancelTrip: (token: string, id: string) =>
    apiClient.patch<Trip>(`/fleet/trips/${id}/cancel`, {}, token),
  closeTrip: (token: string, id: string, payload: TripCloseInput) =>
    apiClient.patch<TripCloseResult>(`/fleet/trips/${id}/close`, payload, token),

  /** RF-14: gastos de todos los viajes, filtrados por vehículo, conductor, tipo o fechas. */
  queryExpenses: (token: string, filters: ExpenseFilters = {}) =>
    apiClient.get<ExpenseRow[]>(`/fleet/expenses${queryString({ ...filters })}`, token),
  listExpenses: (token: string, tripId: string) =>
    apiClient.get<Expense[]>(`/fleet/trips/${tripId}/expenses`, token),
  createExpense: (token: string, tripId: string, payload: ExpenseInput) =>
    apiClient.post<Expense>(`/fleet/trips/${tripId}/expenses`, payload, token),

  // Costos fijos por vehículo y de personal por conductor (modelo de costos): solo el rol admin.
  listFixedCosts: (token: string) => apiClient.get<FixedCost[]>("/fleet/fixed-costs", token),
  createFixedCost: (token: string, payload: FixedCostInput) => apiClient.post<FixedCost>("/fleet/fixed-costs", payload, token),
  updateFixedCost: (token: string, id: string, payload: Partial<FixedCostInput>) =>
    apiClient.patch<FixedCost>(`/fleet/fixed-costs/${id}`, payload, token),
  deleteFixedCost: (token: string, id: string) => apiClient.delete(`/fleet/fixed-costs/${id}`, token),
  listPersonnelCosts: (token: string) => apiClient.get<PersonnelCost[]>("/fleet/personnel-costs", token),
  createPersonnelCost: (token: string, payload: PersonnelCostInput) =>
    apiClient.post<PersonnelCost>("/fleet/personnel-costs", payload, token),
  updatePersonnelCost: (token: string, id: string, payload: Partial<PersonnelCostInput>) =>
    apiClient.patch<PersonnelCost>(`/fleet/personnel-costs/${id}`, payload, token),
  deletePersonnelCost: (token: string, id: string) => apiClient.delete(`/fleet/personnel-costs/${id}`, token),

  listVehicleMaintenance: (token: string, vehicleId: string) =>
    apiClient.get<MaintenanceRecord[]>(`/fleet/vehicles/${vehicleId}/maintenance`, token),
  createMaintenance: (token: string, vehicleId: string, payload: MaintenanceInput) =>
    apiClient.post<MaintenanceRecord>(`/fleet/vehicles/${vehicleId}/maintenance`, payload, token),
  completeMaintenance: (token: string, id: string, payload: MaintenanceCompleteInput) =>
    apiClient.patch<MaintenanceRecord>(`/fleet/maintenance/${id}/complete`, payload, token),
  listMaintenanceAlerts: (token: string) =>
    apiClient.get<MaintenanceRecord[]>("/fleet/maintenance/alerts", token),
  maintenancePolicy: (token: string) =>
    apiClient.get<MaintenancePolicy>("/fleet/maintenance/policy", token),
};
