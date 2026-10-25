/**
 * Cliente del portal de despacho (RF-18): llamadas a /api/fleet/despacho/* sin sesión,
 * autenticadas con la credencial personal del código QR.
 */
import { apiClient } from "./apiClient";
import type { DespachoInfo, DespachoInput, DespachoResult } from "../types/despacho";

/** Nombre de la cabecera con la credencial personal del QR (ver qr_token.py en fleet-core-service). */
const TOKEN_HEADER = "X-Despacho-Token";

/** Sin token de sesión: el conductor no inicia sesión. La credencial del QR viaja en una
 * cabecera (no en la URL de la API) para que no quede en los registros de acceso del gateway;
 * el backend la compara contra el hash guardado y verifica su vigencia. */
export const despachoApi = {
  getInfo: (driverId: string, qrToken: string) =>
    apiClient.get<DespachoInfo>(`/fleet/despacho/${driverId}`, null, { [TOKEN_HEADER]: qrToken }),
  registrarSalida: (driverId: string, qrToken: string, payload: DespachoInput) =>
    apiClient.post<DespachoResult>(`/fleet/despacho/${driverId}`, payload, null, { [TOKEN_HEADER]: qrToken }),
};
