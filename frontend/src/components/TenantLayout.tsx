import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, Building, LogOut, Menu, DollarSign,
  UserCircle, CalendarDays, BarChart2, CalendarRange, Kanban, Euro,
  Lock, ChevronDown,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useState, useRef, useEffect } from 'react';
import NotificationBell from './NotificationBell';
import ChangePasswordModal from './ChangePasswordModal';

function UserMenu({ onChangePassword, onLogout, displayName, role }: {
  onChangePassword: () => void;
  onLogout: () => void;
  displayName: string;
  role: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold">
          {displayName.charAt(0).toUpperCase()}
        </div>
        <span className="hidden sm:block max-w-[120px] truncate">{displayName}</span>
        <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-10 w-52 rounded-xl bg-white shadow-xl ring-1 ring-slate-900/10 z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-sm font-semibold text-slate-900 truncate">{displayName}</p>
            <p className="text-xs text-slate-500 uppercase font-medium mt-0.5">{role}</p>
          </div>
          <div className="py-1">
            <button
              onClick={() => { setOpen(false); onChangePassword(); }}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <Lock className="h-4 w-4 text-slate-400" />
              Cambiar contraseña
            </button>
            <button
              onClick={() => { setOpen(false); onLogout(); }}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Cerrar sesión
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TenantLayout() {
  const { user, logout } = useAuth();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(
    Boolean(user?.mustChangePassword),
  );
  const navigate = useNavigate();

  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';
  const passwordChangeRequired = Boolean(user?.mustChangePassword);
  const displayName = user?.fullName || user?.email || '';

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, show: true },
    { name: 'Propiedades', href: '/properties', icon: Building, show: true },
    { name: 'Pipeline', href: '/kanban', icon: Kanban, show: true },
    { name: 'Clientes', href: '/clients', icon: UserCircle, show: true },
    { name: 'Visitas', href: '/visits', icon: CalendarDays, show: true },
    { name: 'Calendario', href: '/calendar', icon: CalendarRange, show: true },
    { name: 'Ventas', href: '/sales', icon: DollarSign, show: true },
    { name: 'Reportes', href: '/reports', icon: BarChart2, show: isManager },
    { name: 'Comisiones', href: '/commissions', icon: Euro, show: isManager },
    { name: 'Empleados', href: '/employees', icon: Users, show: isManager },
  ].filter(item => item.show);

  const handleLogout = () => logout().then(() => navigate('/login'));

  return (
    <div className="flex bg-slate-50 min-h-screen">
      {/* Sidebar — desktop only */}
      <aside className="hidden w-64 flex-col border-r border-slate-200 bg-white md:flex transition-all">
        <div className="flex h-16 items-center border-b border-slate-200 px-6">
          <div className="flex items-center space-x-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
              <Building className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-900">RealtyApp</span>
          </div>
        </div>
        <div className="flex flex-1 flex-col overflow-y-auto px-4 py-6">
          <nav className="flex-1 space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={({ isActive }) =>
                    `group flex items-center space-x-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon className={`h-5 w-5 ${isActive ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                      <span>{item.name}</span>
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top header — always visible */}
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4">
          {/* Left: logo on mobile, empty on desktop */}
          <div className="flex items-center gap-2 md:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
              <Building className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-900">RealtyApp</span>
          </div>
          <div className="hidden md:block" />

          {/* Right: notifications + user menu + mobile hamburger */}
          <div className="flex items-center gap-1">
            <NotificationBell />
            <UserMenu
              displayName={displayName}
              role={user?.role ?? ''}
              onChangePassword={() => setShowChangePassword(true)}
              onLogout={handleLogout}
            />
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="ml-1 rounded-lg p-2 text-slate-500 hover:bg-slate-100 md:hidden"
            >
              <Menu className="h-6 w-6" />
            </button>
          </div>
        </header>

        {/* Mobile nav drawer */}
        {isMobileMenuOpen && (
          <div className="md:hidden border-b border-slate-200 bg-white px-4 py-3">
            <nav className="flex flex-col space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center space-x-3 rounded-lg px-3 py-2 text-base font-medium ${
                        isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600'
                      }`
                    }
                  >
                    <Icon className="h-5 w-5" />
                    <span>{item.name}</span>
                  </NavLink>
                );
              })}
            </nav>
          </div>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>

      {showChangePassword && (
        <ChangePasswordModal
          required={passwordChangeRequired}
          onClose={() => setShowChangePassword(false)}
        />
      )}
    </div>
  );
}
