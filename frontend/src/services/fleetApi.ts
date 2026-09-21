// Llamadas HTTP a fleet-core-service (vía el gateway): vehículos,
// conductores, viajes, gastos y mantenimiento.
import { apiClient } from "./apiClient";
import type { Driver, DriverInput, DriverQrIssued, Vehicle, VehicleInput } from "../types/fleet";
import type {
  Expense,
  ExpenseInput,
  Trip,
  TripCloseInput,
  TripCloseResult,
  TripInput,
} from "../types/trips";
import type {
  MaintenanceCompleteInput,
  MaintenanceInput,
  MaintenancePolicy,
  MaintenanceRecord,
} from "../types/maintenance";

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
  regenerateDriverQr: (token: string, id: string) =>
    apiClient.post<DriverQrIssued>(`/fleet/drivers/${id}/regenerate-qr`, {}, token),
  revokeDriverQr: (token: string, id: string) =>
    apiClient.post<Driver>(`/fleet/drivers/${id}/revoke-qr`, {}, token),

  listTrips: (token: string) => apiClient.get<Trip[]>("/fleet/trips", token),
  getTrip: (token: string, id: string) => apiClient.get<Trip>(`/fleet/trips/${id}`, token),
  createTrip: (token: string, payload: TripInput) =>
    apiClient.post<Trip>("/fleet/trips", payload, token),
  startTrip: (token: string, id: string) =>
    apiClient.patch<Trip>(`/fleet/trips/${id}/start`, {}, token),
  cancelTrip: (token: string, id: string) =>
    apiClient.patch<Trip>(`/fleet/trips/${id}/cancel`, {}, token),
  closeTrip: (token: string, id: string, payload: TripCloseInput) =>
    apiClient.patch<TripCloseResult>(`/fleet/trips/${id}/close`, payload, token),

  listExpenses: (token: string, tripId: string) =>
    apiClient.get<Expense[]>(`/fleet/trips/${tripId}/expenses`, token),
  createExpense: (token: string, tripId: string, payload: ExpenseInput) =>
    apiClient.post<Expense>(`/fleet/trips/${tripId}/expenses`, payload, token),

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
