import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Users, Building, LogOut, Menu, DollarSign, UserCircle, CalendarDays, BarChart2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useState } from 'react';

export default function TenantLayout() {
  const { user, logout } = useAuth();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, show: true },
    { name: 'Propiedades', href: '/properties', icon: Building, show: true },
    { name: 'Clientes', href: '/clients', icon: UserCircle, show: true },
    { name: 'Visitas', href: '/visits', icon: CalendarDays, show: true },
    { name: 'Ventas', href: '/sales', icon: DollarSign, show: true },
    { name: 'Reportes', href: '/reports', icon: BarChart2, show: isManager },
    { name: 'Empleados', href: '/employees', icon: Users, show: isManager },
  ].filter(item => item.show);

  return (
    <div className="flex bg-slate-50 min-h-screen">
      {/* Sidebar for Desktop */}
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
        <div className="border-t border-slate-200 p-4">
          <div className="xs:hidden mb-4 flex items-center px-2">
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{user?.fullName || user?.email}</p>
              <p className="truncate text-xs font-medium text-slate-500 uppercase">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="group flex w-full items-center space-x-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition-all hover:bg-red-50 hover:text-red-700"
          >
            <LogOut className="h-5 w-5 text-slate-400 group-hover:text-red-600" />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </aside>

      {/* Main Content Wrapper */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile Header */}
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden">
          <div className="flex items-center space-x-2">
             <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
              <Building className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-900">RealtyApp</span>
          </div>
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
          >
            <Menu className="h-6 w-6" />
          </button>
        </header>

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
                          isActive
                            ? 'bg-indigo-50 text-indigo-700'
                            : 'text-slate-600'
                        }`
                      }
                    >
                      <Icon className="h-5 w-5" />
                      <span>{item.name}</span>
                    </NavLink>
                  )
               })}
             </nav>
          </div>
        )}

        {/* Dashboard Content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
