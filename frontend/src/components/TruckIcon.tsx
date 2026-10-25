/**
 * Ícono decorativo de camión para la portada de acceso y los estados vacíos.
 */
import { Truck } from "lucide-react";

/** Ícono decorativo (portada de login, estados vacíos) -- no es la marca, ver Logo.tsx. */
function TruckIcon({ size = 56 }: { size?: number }) {
  return <Truck size={size} color="var(--brand-accent)" strokeWidth={2} aria-hidden="true" />;
}

export default TruckIcon;
