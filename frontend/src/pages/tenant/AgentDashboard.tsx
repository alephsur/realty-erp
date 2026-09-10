import { useState, useEffect } from 'react';
import { Home, TrendingUp, DollarSign, CheckCircle2, Clock, MapPin, Users, CalendarDays } from 'lucide-react';
import client from '../../api/client';

interface AgentStats {
  total_properties: number;
  active_properties: number;
  sold_properties: number;
  total_sales: number;
  total_commission: number;
  total_volume: number;
}

interface PropertyData {
  id: string;
  title: string;
  address: string;
  city: string | null;
  price: number;
  status: string | null;
  status_key: string | null;
  reference: string | null;
  property_type: string | null;
}

interface VisitData {
  id: string;
  property_title: string | null;
  property_address: string | null;
  client_name: string | null;
  scheduled_at: string | null;
  status: string | null;
}

interface PaginatedResponse<T> {
  items: T[];
}

const STATUS_COLORS: Record<string, string> = {
  CAPTADA: 'bg-slate-100 text-slate-800',
  PUBLICADA: 'bg-blue-100 text-blue-800',
  EN_VISITAS: 'bg-amber-100 text-amber-800',
  RESERVADA: 'bg-purple-100 text-purple-800',
  PENDIENTE_NOTARIA: 'bg-orange-100 text-orange-800',
  VENDIDA: 'bg-emerald-100 text-emerald-800',
  RETIRADA: 'bg-red-100 text-red-800',
};

const STATUS_LABELS: Record<string, string> = {
  CAPTADA: 'Captada',
  PUBLICADA: 'Publicada',
  EN_VISITAS: 'En Visitas',
  RESERVADA: 'Reservada',
  PENDIENTE_NOTARIA: 'Pte. Notaría',
  VENDIDA: 'Vendida',
  RETIRADA: 'Retirada',
};

export default function AgentDashboard() {
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [properties, setProperties] = useState<PropertyData[]>([]);
  const [visits, setVisits] = useState<VisitData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setError(null);
        const [statsRes, propsRes, visitsRes] = await Promise.all([
          client.get<AgentStats>('/properties/stats/agent-summary'),
          client.get<PaginatedResponse<PropertyData>>('/properties/my', { params: { limit: 200 } }),
          client.get<PaginatedResponse<VisitData>>('/visits/my', { params: { limit: 200 } }),
        ]);
        setStats(statsRes.data);
        setProperties(propsRes.data.items);
        setVisits(visitsRes.data.items);
      } catch (err) {
        console.error(err);
        setError('No se pudo cargar la información del agente. Inténtalo de nuevo.');
      }
      finally { setLoading(false); }
    };
    fetchData();
  }, []);

  const kpiCards = stats ? [
    { name: 'Mis Propiedades', value: String(stats.active_properties), icon: Home, detail: `${stats.total_properties} total asignadas`, color: 'bg-indigo-50 border-indigo-100 text-indigo-600' },
    { name: 'Ventas Cerradas', value: String(stats.total_sales), icon: CheckCircle2, detail: `${stats.sold_properties} propiedades vendidas`, color: 'bg-emerald-50 border-emerald-100 text-emerald-600' },
    { name: 'Comisión Acumulada', value: `${stats.total_commission.toLocaleString('es-ES')} €`, icon: DollarSign, detail: 'Total ganado en comisiones', color: 'bg-amber-50 border-amber-100 text-amber-600' },
    { name: 'Volumen de Ventas', value: `${stats.total_volume.toLocaleString('es-ES')} €`, icon: TrendingUp, detail: 'Total vendido', color: 'bg-purple-50 border-purple-100 text-purple-600' },
  ] : [];

  if (loading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div></div>;
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Mi Panel</h1>
        <p className="text-slate-500 mt-1">Resumen de tu actividad como agente inmobiliario.</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {kpiCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.name} className="bg-white rounded-2xl p-6 shadow-sm ring-1 ring-slate-900/5 hover:relative hover:-translate-y-1 hover:shadow-md transition-all duration-300">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">{stat.name}</p>
                  <p className="text-3xl font-bold text-slate-900 mt-2">{stat.value}</p>
                </div>
                <div className={`h-12 w-12 rounded-xl flex items-center justify-center border ${stat.color}`}>
                  <Icon className="h-6 w-6" />
                </div>
              </div>
              <p className="text-sm font-medium text-slate-500 mt-4">{stat.detail}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Upcoming Visits */}
        <div className="bg-white rounded-2xl ring-1 ring-slate-900/5 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Próximas Visitas</h2>
          </div>
          <div className="divide-y divide-slate-100">
            {visits.length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-sm">No tienes visitas programadas.</div>
            ) : (
              visits.slice(0, 5).map(v => (
                <div key={v.id} className="px-6 py-4 hover:bg-slate-50/50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{v.property_title}</p>
                      <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3" />{v.property_address}
                      </p>
                      {v.client_name && (
                        <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                          <Users className="w-3 h-3" />{v.client_name}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-indigo-600 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {v.scheduled_at ? new Date(v.scheduled_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' }) : '—'}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {v.scheduled_at ? new Date(v.scheduled_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }) : ''}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* My Properties */}
        <div className="bg-white rounded-2xl ring-1 ring-slate-900/5 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-2">
            <Home className="h-5 w-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Mis Propiedades Activas</h2>
          </div>
          <div className="divide-y divide-slate-100">
            {properties.filter(p => p.status_key !== 'VENDIDA' && p.status_key !== 'RETIRADA').length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-sm">No tienes propiedades activas asignadas.</div>
            ) : (
              properties
                .filter(p => p.status_key !== 'VENDIDA' && p.status_key !== 'RETIRADA')
                .slice(0, 6)
                .map(p => (
                  <div key={p.id} className="px-6 py-4 hover:bg-slate-50/50 transition-colors">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-slate-900">{p.title}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{p.address}{p.city ? `, ${p.city}` : ''}</p>
                        {p.reference && <p className="text-xs text-slate-400 mt-0.5">Ref: {p.reference}</p>}
                      </div>
                      <div className="flex flex-col items-end gap-1.5">
                        <span className="text-sm font-semibold text-slate-900">{p.price.toLocaleString('es-ES')} €</span>
                        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${STATUS_COLORS[p.status_key || ''] || 'bg-slate-100 text-slate-800'}`}>
                          {STATUS_LABELS[p.status_key || ''] || p.status || '—'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
