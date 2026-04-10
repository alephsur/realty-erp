import { Building2, TrendingUp, Users, CheckCircle2, Home, DollarSign } from 'lucide-react';
import { useState, useEffect } from 'react';
import client from '../../api/client';

interface Stats {
  total_properties: number;
  active_properties: number;
  sold_properties: number;
  total_agents: number;
  total_revenue: number;
  total_sales: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const r = await client.get('/properties/stats/summary');
        setStats(r.data);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    };
    fetchStats();
  }, []);

  const cards = stats ? [
    { name: 'Total Propiedades', value: String(stats.total_properties), icon: Home, detail: `${stats.active_properties} activas` },
    { name: 'Agentes', value: String(stats.total_agents), icon: Users, detail: 'Agentes registrados' },
    { name: 'Ventas Cerradas', value: String(stats.total_sales), icon: CheckCircle2, detail: `${stats.sold_properties} propiedades vendidas` },
    { name: 'Ingresos (Comisiones)', value: `${stats.total_revenue.toLocaleString('es-ES')} €`, icon: DollarSign, detail: 'Total ganado' },
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
                  <div className="h-12 w-12 rounded-xl bg-indigo-50 flex items-center justify-center border border-indigo-100">
                    <Icon className="h-6 w-6 text-indigo-600" />
                  </div>
                </div>
                <p className="text-sm font-medium text-emerald-600 mt-4">{stat.detail}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
