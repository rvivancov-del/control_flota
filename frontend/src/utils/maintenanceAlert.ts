/** Texto de una alerta de mantenimiento por kilometraje (RF-13). La clasificación
 * vencido / próximo la decide fleet-core-service; aquí solo se redacta. */
export type AlertUrgency = "vencido" | "proximo";

const km = (value: number) => Math.abs(value).toLocaleString("es-EC");

export function describeUrgency(urgency: string | null | undefined, kmRemaining: number | null | undefined): string {
  if (urgency === "vencido") {
    return kmRemaining != null && kmRemaining < 0 ? `vencido hace ${km(kmRemaining)} km` : "vence ahora";
  }
  if (urgency === "proximo") {
    return kmRemaining != null ? `próximo: faltan ${km(kmRemaining)} km` : "próximo";
  }
  return "";
}
