import { FileSpreadsheet, Route, Truck, UserRound, Users, Wallet, Wrench, type LucideIcon } from "lucide-react";

export type NavItem = {
  path: string;
  label: string;
  description: string;
  icon: LucideIcon;
  adminOnly?: boolean;
};

/** Los 7 módulos del sistema (además de Dashboard, Mi perfil y Login, que no
 * llevan tarjeta propia) — cada tarjeta del dashboard y cada ítem del menú
 * lateral enlaza a uno de estos. Todos están implementados; no hay módulos
 * pendientes ni páginas de relleno. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/vehiculos", label: "Vehículos", description: "Alta, edición y consulta de la flota", icon: Truck },
  { path: "/conductores", label: "Conductores", description: "Alta, edición y consulta de conductores", icon: UserRound },
  { path: "/viajes", label: "Viajes", description: "Registrar, iniciar, cerrar y consultar viajes", icon: Route },
  { path: "/mantenimiento", label: "Mantenimiento", description: "Registros, alertas por kilometraje", icon: Wrench },
  { path: "/reportes", label: "Reportes", description: "Costos y mantenimientos por período; exportación a Excel y PDF (administrador)", icon: FileSpreadsheet },
  { path: "/costos", label: "Costos", description: "Costos fijos por vehículo y personal por conductor (administrador)", icon: Wallet, adminOnly: true },
  { path: "/usuarios", label: "Usuarios", description: "Gestión de cuentas y roles", icon: Users, adminOnly: true },
];
