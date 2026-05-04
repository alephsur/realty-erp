import { Building2, TrendingUp, Users, CheckCircle2, Home, DollarSign, AlertTriangle, Trophy } from 'lucide-react';
import { useState, useEffect } from 'react';
import client from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import AgentDashboard from './AgentDashboard';

interface Stats {
  total_properties: number;
  active_properties: number;
  sold_properties: number;
  total_agents: number;
  total_revenue: number;
  total_sales: number;
  unassigned_properties: number;
}

interface AgentRank {
  id: string;
  full_name: string;
  email: string;
  active_properties: number;
  total_sales: number;
  total_commission: number;
  total_volume: number;
  commission_rate: number;
}

export default function Dashboard() {
  const { user } = useAuth();
  
  // If the user is an AGENT, render a dedicated agent dashboard
  if (user?.role === 'AGENT') {
    return <AgentDashboard />;
  }

  return <ManagerDashboard />;
}

function ManagerDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [ranking, setRanking] = useState<AgentRank[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, rankingRes] = await Promise.all([
          client.get('/properties/stats/summary'),
          client.get('/properties/stats/agent-ranking'),
        ]);
        setStats(statsRes.data);
        setRanking(rankingRes.data);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    };
    fetchData();
  }, []);

  const cards = stats ? [
    { name: 'Total Propiedades', value: String(stats.total_properties), icon: Home, detail: `${stats.active_properties} activas`, color: 'text-indigo-600 bg-indigo-50 border-indigo-100' },
    { name: 'Agentes', value: String(stats.total_agents), icon: Users, detail: 'Agentes registrados', color: 'text-blue-600 bg-blue-50 border-blue-100' },
    { name: 'Ventas Cerradas', value: String(stats.total_sales), icon: CheckCircle2, detail: `${stats.sold_properties} propiedades vendidas`, color: 'text-emerald-600 bg-emerald-50 border-emerald-100' },
    { name: 'Ingresos (Comisiones)', value: `${stats.total_revenue.toLocaleString('es-ES')} €`, icon: DollarSign, detail: 'Total ganado', color: 'text-amber-600 bg-amber-50 border-amber-100' },
  ] : [];

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1">Resumen de tu negocio inmobiliario.</p>
      </div>

      {loading ? (
        <div className="text-center text-slate-500 py-8">Cargando estadísticas...</div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {cards.map((stat) => {
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
                  <p className="text-sm font-medium text-emerald-600 mt-4">{stat.detail}</p>
                </div>
              );
            })}
          </div>

          {/* Alert: unassigned properties */}
          {stats && stats.unassigned_properties > 0 && (
            <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
              <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0" />
              <div>
                <p className="text-sm font-semibold text-amber-800">
                  {stats.unassigned_properties} propiedad{stats.unassigned_properties > 1 ? 'es' : ''} sin agente asignado
                </p>
                <p className="text-xs text-amber-600 mt-0.5">Ve a Propiedades para asignar un agente responsable.</p>
              </div>
            </div>
          )}

          {/* Agent Ranking */}
          {ranking.length > 0 && (
            <div className="bg-white rounded-2xl ring-1 ring-slate-900/5 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-2">
                <Trophy className="h-5 w-5 text-amber-500" />
                <h2 className="text-base font-bold text-slate-900">Ranking de Agentes</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead>
                    <tr className="bg-slate-50">
                      <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">#</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Agente</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Prop. Activas</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Ventas</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Comisión Total</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Volumen</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-slate-200">
                    {ranking.map((agent, idx) => (
                      <tr key={agent.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                            idx === 0 ? 'bg-amber-100 text-amber-800' : idx === 1 ? 'bg-slate-200 text-slate-700' : idx === 2 ? 'bg-orange-100 text-orange-800' : 'bg-slate-100 text-slate-600'
                          }`}>{idx + 1}</span>
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-3">
                            <div className="h-9 w-9 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm">
                              {agent.full_name?.charAt(0).toUpperCase() || '?'}
                            </div>
                            <div>
                              <p className="text-sm font-medium text-slate-900">{agent.full_name}</p>
                              <p className="text-xs text-slate-500">{agent.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-sm font-medium text-slate-700">{agent.active_properties}</td>
                        <td className="px-4 py-4 text-sm font-medium text-slate-700">{agent.total_sales}</td>
                        <td className="px-4 py-4 text-sm font-semibold text-emerald-700">{agent.total_commission.toLocaleString('es-ES')} €</td>
                        <td className="px-4 py-4 text-sm text-slate-600">{agent.total_volume.toLocaleString('es-ES')} €</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
