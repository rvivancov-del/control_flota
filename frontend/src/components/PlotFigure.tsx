/**
 * Adaptador de Observable Plot a React: lo usan las gráficas del tablero y de reportes
 * (definidas en charts/expensePlots.ts).
 */
import { useEffect, useRef } from "react";

type PlotFigureProps = {
  render: (width: number) => (SVGElement | HTMLElement) | null;
  deps: unknown[];
  height?: number;
};

/** Envuelve Observable Plot (imperativo, genera un <svg> propio) para usarlo
 * como componente React declarativo: redibuja cuando cambian `deps` o el
 * ancho del contenedor, y limpia el nodo anterior en cada redibujo. */
function PlotFigure({ render, deps, height = 260 }: PlotFigureProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const renderRef = useRef(render);
  renderRef.current = render;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let currentEl: (SVGElement | HTMLElement) | null = null;

    const draw = () => {
      const width = container.clientWidth || 480;
      if (currentEl) {
        currentEl.remove();
        currentEl = null;
      }
      const el = renderRef.current(width);
      if (el) {
        container.append(el);
        currentEl = el;
      }
    };

    draw();
    const observer = new ResizeObserver(() => draw());
    observer.observe(container);

    return () => {
      observer.disconnect();
      if (currentEl) currentEl.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}

export default PlotFigure;
