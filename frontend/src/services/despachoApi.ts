import { apiClient } from "./apiClient";
import type { DespachoInfo, DespachoInput, DespachoResult } from "../types/despacho";

/** Sin token de sesión: el conductor no inicia sesión, el token del QR
 * viaja como query param y el backend lo valida contra Driver.qr_token. */
export const despachoApi = {
  getInfo: (driverId: string, qrToken: string) =>
    apiClient.get<DespachoInfo>(`/fleet/despacho/${driverId}?token=${encodeURIComponent(qrToken)}`),
  registrarSalida: (driverId: string, qrToken: string, payload: DespachoInput) =>
    apiClient.post<DespachoResult>(`/fleet/despacho/${driverId}?token=${encodeURIComponent(qrToken)}`, payload),
};
