/**
 * Estructura común de las páginas autenticadas: menú lateral filtrado por rol (nav.ts),
 * encabezado con el usuario en sesión y cierre de sesión.
 */
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { LayoutDashboard, LogOut } from "lucide-react";
import Logo from "./Logo";
import { useAuth } from "../context/AuthContext";
import { NAV_ITEMS } from "../nav";
import styles from "./AppShell.module.css";

/** Layout común de las páginas autenticadas: barra lateral con navegación
 * (filtrada por rol) + encabezado con el usuario actual y cerrar sesión. */
function AppShell({ title, children }: { title: string; children: ReactNode }) {
  const { user, logout } = useAuth();
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || user?.role.name === "admin");

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <Logo size={34} tone="inverted" />
          <div>
            <div className={styles.brandName}>FlotaControl</div>
            <div className={styles.brandTag}>Cada kilómetro, bajo control.</div>
          </div>
        </div>

        <nav className={styles.nav}>
          <span className={styles.navSectionLabel}>Panel</span>
          <NavLink
            to="/"
            end
            className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ""}`}
          >
            <LayoutDashboard size={17} strokeWidth={2} />
            Dashboard
          </NavLink>

          <span className={styles.navSectionLabel} style={{ marginTop: "1rem" }}>
            Operación
          </span>
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ""}`}
            >
              <item.icon size={17} strokeWidth={2} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className={styles.sidebarFooter}>
          Trabajo de titulación — UNEMI
          <br />
          Rosa Margarita Vivanco Velez
        </div>
      </aside>

      <div className={styles.main}>
        <header className={styles.topbar}>
          <h1 className={styles.pageTitle}>{title}</h1>
          <div className={styles.userBlock}>
            <div className={styles.userInfo}>
              <div className={styles.userName}>{user?.full_name ?? user?.username}</div>
              <div className={styles.userRole}>{user?.role.name}</div>
            </div>
            <button type="button" className={styles.logoutButton} onClick={logout}>
              <LogOut size={15} strokeWidth={2} />
              Cerrar sesión
            </button>
          </div>
        </header>
        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
}

export default AppShell;
