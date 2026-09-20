/**
 * Tarifas de IVA vigentes en Ecuador (2026) por categoría de gasto, según la
 * Ley de Régimen Tributario Interno (Art. 56) y la Circular del SRI de
 * diciembre de 2025 que mantiene la tarifa general en 15%.
 *
 * - Combustibles (diésel, gasolina): tarifa 0% — exentos explícitamente.
 * - Peaje: tarifa 0% — uso de vías y puentes, exento.
 * - Alimentación (comida preparada en ruta) y mantenimiento (repuestos y
 *   mano de obra): tarifa general 15%.
 *
 * Estas tarifas son la ley vigente, no un dato editable por el usuario, así
 * que se derivan del monto total ya registrado (lo que realmente salió de
 * caja) en vez de pedir que alguien las calcule a mano. Si el SRI cambia una
 * tarifa, este es el único lugar que hay que actualizar.
 */
export type TaxableCategory = "combustible" | "peaje" | "alimentacion" | "mantenimiento";

export const IVA_RATES: Record<TaxableCategory, number> = {
  combustible: 0,
  peaje: 0,
  alimentacion: 0.15,
  mantenimiento: 0.15,
};

export const IVA_RATE_LABELS: Record<TaxableCategory, string> = {
  combustible: "Exento (Art. 56 LRTI)",
  peaje: "Exento (Art. 56 LRTI)",
  alimentacion: "15%",
  mantenimiento: "15%",
};

export type IvaBreakdown = {
  subtotal: number;
  iva: number;
  total: number;
  rate: number;
};

/** Descompone un monto total (IVA incluido) en base imponible + IVA. */
export function ivaBreakdown(total: number, category: TaxableCategory): IvaBreakdown {
  const rate = IVA_RATES[category];
  const subtotal = total / (1 + rate);
  return { subtotal, iva: total - subtotal, total, rate };
}
