/**
 * Marca FlotaControl (logotipo vectorial) usada en el menú lateral y en las pantallas de acceso.
 */
import { Truck } from "lucide-react";

type LogoProps = {
  size?: number;
  tone?: "default" | "inverted";
  className?: string;
};

/**
 * Marca FlotaControl: un hexágono (sistema/red — más tecnológico que un
 * círculo) enmarca el ícono real de camión de Lucide (lucide-react, MIT),
 * con tres trazos de "velocidad" como acento de movimiento — en vez de un
 * camión dibujado a mano, que se veía genérico e infantil.
 */
function Logo({ size = 40, tone = "default", className }: LogoProps) {
  const structural = tone === "inverted" ? "#ffffff" : "var(--brand-navy)";
  const accent = "var(--brand-accent)";

  return (
    <div
      className={className}
      role="img"
      aria-label="FlotaControl"
      style={{ position: "relative", width: size, height: size * 1.08, display: "inline-block" }}
    >
      <svg
        width={size}
        height={size * 1.08}
        viewBox="0 0 100 108"
        style={{ position: "absolute", inset: 0 }}
      >
        <polygon
          points="88,58 69,90.9 31,90.9 12,58 31,25.1 69,25.1"
          fill="none"
          stroke={structural}
          strokeWidth="4.5"
          strokeLinejoin="round"
        />
        <line x1="18" y1="60" x2="31" y2="51.5" stroke={accent} strokeWidth="3.2" strokeLinecap="round" />
        <line x1="18" y1="69" x2="31" y2="60.5" stroke={accent} strokeWidth="3.2" strokeLinecap="round" />
        <line x1="18" y1="78" x2="31" y2="69.5" stroke={accent} strokeWidth="3.2" strokeLinecap="round" />
      </svg>
      <Truck
        size={size * 0.46}
        color={structural}
        strokeWidth={2.3}
        style={{
          position: "absolute",
          top: "54%",
          left: "53%",
          transform: "translate(-50%, -50%)",
        }}
      />
    </div>
  );
}

export default Logo;
