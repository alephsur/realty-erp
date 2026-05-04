import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import AcceptInvite from './pages/AcceptInvite';
import SuperAdminDashboard from './pages/SuperAdminDashboard';
import TenantLayout from './components/TenantLayout';
import Dashboard from './pages/tenant/Dashboard';
import Employees from './pages/tenant/Employees';
import Properties from './pages/tenant/Properties';
import Sales from './pages/tenant/Sales';
import Clients from './pages/tenant/Clients';
import Visits from './pages/tenant/Visits';
import Reports from './pages/tenant/Reports';
import CalendarPage from './pages/tenant/Calendar';
import PropertyKanban from './pages/tenant/PropertyKanban';

const Unauthorized = () => <div className="flex justify-center items-center h-screen text-2xl font-bold text-slate-800">403 Unauthorized Access</div>;

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/accept-invite" element={<AcceptInvite />} />
          <Route path="/unauthorized" element={<Unauthorized />} />
          
          <Route element={<ProtectedRoute />}>
            
            {/* SuperAdmin route */}
            <Route element={<ProtectedRoute allowedRoles={['SUPER_ADMIN']} />}>
              <Route path="/superadmin" element={<SuperAdminDashboard />} />
            </Route>

            {/* Tenant routes — all authenticated tenant roles */}
            <Route element={<ProtectedRoute allowedRoles={['MANAGER', 'ADMIN', 'AGENT']} />}>
              <Route element={<TenantLayout />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/properties" element={<Properties />} />
                <Route path="/kanban" element={<PropertyKanban />} />
                <Route path="/clients" element={<Clients />} />
                <Route path="/visits" element={<Visits />} />
                <Route path="/calendar" element={<CalendarPage />} />
                <Route path="/sales" element={<Sales />} />
                <Route index element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Route>

            {/* Manager/Admin-only routes — agents are redirected to /unauthorized */}
            <Route element={<ProtectedRoute allowedRoles={['MANAGER', 'ADMIN']} />}>
              <Route element={<TenantLayout />}>
                <Route path="/employees" element={<Employees />} />
                <Route path="/reports" element={<Reports />} />
              </Route>
            </Route>
          </Route>
          
          {/* Default fallback catch-all */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
