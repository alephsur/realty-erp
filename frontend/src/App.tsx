import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import ProtectedRoute from './components/ProtectedRoute';

// Placeholder Pages
const Login = () => <div className="p-8 text-xl">Login Page (mock)</div>;
const Dashboard = () => <div className="p-8 text-xl bg-orange-100 min-h-screen">Dashboard (Managers only)</div>;
const Properties = () => <div className="p-8 text-xl bg-blue-100 min-h-screen">Properties (All authenticated)</div>;
const Unauthorized = () => <div className="p-8 text-xl text-red-500">403 Unauthorized</div>;

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/unauthorized" element={<Unauthorized />} />
          
          <Route element={<ProtectedRoute />}>
            <Route path="/properties" element={<Properties />} />
            
            {/* Role based guard */}
            <Route element={<ProtectedRoute allowedRoles={['MANAGER', 'ADMIN']} />}>
              <Route path="/dashboard" element={<Dashboard />} />
            </Route>
          </Route>
          
          <Route path="*" element={<Login />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
