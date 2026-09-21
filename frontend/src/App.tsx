// Mapa de rutas del SPA. /login y /despacho quedan fuera de ProtectedRoute
// a propósito: /despacho es el portal del conductor (RF-18), que se abre
// desde un código QR sin sesión de administrador.
import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import DespachoPage from "./pages/DespachoPage";
import DashboardPage from "./pages/DashboardPage";
import ProfilePage from "./pages/ProfilePage";
import VehiclesPage from "./pages/VehiclesPage";
import DriversPage from "./pages/DriversPage";
import TripsPage from "./pages/TripsPage";
import TripDetailPage from "./pages/TripDetailPage";
import MaintenancePage from "./pages/MaintenancePage";
import UsersPage from "./pages/UsersPage";
import ReportsPage from "./pages/ReportsPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import { CHANGE_PASSWORD_PATH } from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";

/** Restringe una ruta ya protegida (sesión iniciada) a usuarios con rol admin. */
function AdminRoute({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  if (user && user.role.name !== "admin") {
    return <Navigate to="/" replace />;
  }
  return children;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/despacho" element={<DespachoPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path={CHANGE_PASSWORD_PATH}
        element={
          <ProtectedRoute>
            <ChangePasswordPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/perfil"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/vehiculos"
        element={
          <ProtectedRoute>
            <VehiclesPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/conductores"
        element={
          <ProtectedRoute>
            <DriversPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/viajes"
        element={
          <ProtectedRoute>
            <TripsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/viajes/:id"
        element={
          <ProtectedRoute>
            <TripDetailPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/mantenimiento"
        element={
          <ProtectedRoute>
            <MaintenancePage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/reportes"
        element={
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/usuarios"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <UsersPage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
