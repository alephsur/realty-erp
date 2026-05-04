import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, Clock, User, Tag } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import client from '../../api/client';

interface PropertyData {
  id: string;
  title: string;
  status_key: string | null;
  price: number;
  address: string;
  reference: string | null;
  agent_name: string | null;
  status_changed_at: string | null;
  created_at: string | null;
}

const COLUMNS = [
  { key: 'CAPTADA',           label: 'Captada',            headerBg: 'bg-slate-500',   cardBorder: 'border-slate-200', stuckDays: 30  },
  { key: 'PUBLICADA',         label: 'Publicada',          headerBg: 'bg-blue-500',    cardBorder: 'border-blue-200',  stuckDays: 60  },
  { key: 'EN_VISITAS',        label: 'En Visitas',         headerBg: 'bg-amber-500',   cardBorder: 'border-amber-200', stuckDays: 30  },
  { key: 'RESERVADA',         label: 'Reservada',          headerBg: 'bg-purple-500',  cardBorder: 'border-purple-200',stuckDays: 15  },
  { key: 'PENDIENTE_NOTARIA', label: 'Pendiente Notaría',  headerBg: 'bg-orange-500',  cardBorder: 'border-orange-200',stuckDays: 15  },
  { key: 'VENDIDA',           label: 'Vendida',            headerBg: 'bg-emerald-500', cardBorder: 'border-emerald-200',stuckDays: null},
];

function daysInStatus(property: PropertyData): number {
  const ref = property.status_changed_at ?? property.created_at;
  if (!ref) return 0;
  return Math.floor((Date.now() - new Date(ref).getTime()) / 86_400_000);
}

function formatPrice(price: number): string {
  return price.toLocaleString('es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
}

export default function PropertyKanban() {
  const { user } = useAuth();
  const [properties, setProperties] = useState<PropertyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overColumn, setOverColumn] = useState<string | null>(null);

  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';

  const fetchProperties = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const all: PropertyData[] = [];
      let page = 1;
      while (true) {
        const res = await client.get('/properties', { params: { page, limit: 200 } });
        all.push(...res.data.items);
        if (page >= res.data.pages) break;
        page++;
      }
      // Exclude retired properties from the pipeline
      setProperties(all.filter(p => p.status_key !== 'RETIRADA'));
    } catch {
      setError('No se pudieron cargar las propiedades.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProperties(); }, [fetchProperties]);

  // ── Drag handlers ──────────────────────────────────────────────────────────

  const onDragStart = (e: React.DragEvent, id: string) => {
    e.dataTransfer.effectAllowed = 'move';
    setDraggingId(id);
  };

  const onDragEnd = () => {
    setDraggingId(null);
    setOverColumn(null);
  };

  const onDragOver = (e: React.DragEvent, colKey: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setOverColumn(colKey);
  };

  const onDrop = async (e: React.DragEvent, colKey: string) => {
    e.preventDefault();
    const id = draggingId;
    setDraggingId(null);
    setOverColumn(null);
    if (!id || !isManager) return;

    const prop = properties.find(p => p.id === id);
    if (!prop || prop.status_key === colKey) return;

    // Optimistic update
    const now = new Date().toISOString();
    setProperties(prev =>
      prev.map(p => p.id === id ? { ...p, status_key: colKey, status_changed_at: now } : p)
    );

    try {
      await client.put(`/properties/${id}`, { status: colKey });
    } catch {
      // Revert on failure
      fetchProperties();
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        Cargando pipeline…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-600">
        {error}
      </div>
    );
  }

  const totalStuck = properties.filter(p => {
    const col = COLUMNS.find(c => c.key === p.status_key);
    return col?.stuckDays !== null && daysInStatus(p) >= (col?.stuckDays ?? Infinity);
  }).length;

  return (
    <div className="p-6 min-h-full">
      {/* Page header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Pipeline Kanban</h1>
          <p className="text-sm text-slate-500 mt-1">
            {isManager
              ? 'Arrastra las tarjetas entre columnas para cambiar el estado.'
              : 'Vista del pipeline de propiedades.'}
          </p>
        </div>
        {totalStuck > 0 && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm font-medium">
            <AlertTriangle className="h-4 w-4" />
            {totalStuck} propiedad{totalStuck > 1 ? 'es' : ''} atascada{totalStuck > 1 ? 's' : ''}
          </div>
        )}
      </div>

      {/* Board */}
      <div className="flex gap-4 overflow-x-auto pb-6">
        {COLUMNS.map(col => {
          const cards = properties.filter(p => p.status_key === col.key);
          const isOver = overColumn === col.key;

          return (
            <div
              key={col.key}
              className={`flex-shrink-0 w-72 rounded-xl border bg-slate-50 flex flex-col transition-all ${
                isOver ? 'ring-2 ring-indigo-400 border-indigo-200' : 'border-slate-200'
              }`}
              onDragOver={isManager ? e => onDragOver(e, col.key) : undefined}
              onDrop={isManager ? e => onDrop(e, col.key) : undefined}
              onDragLeave={() => setOverColumn(null)}
            >
              {/* Column header */}
              <div className={`${col.headerBg} rounded-t-xl px-4 py-3 flex items-center justify-between`}>
                <span className="text-white font-semibold text-sm">{col.label}</span>
                <span className="bg-white/25 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                  {cards.length}
                </span>
              </div>

              {/* Cards */}
              <div className="p-3 space-y-3 flex-1 min-h-20">
                {cards.map(prop => {
                  const days = daysInStatus(prop);
                  const isStuck = col.stuckDays !== null && days >= col.stuckDays;
                  const isDragging = draggingId === prop.id;

                  return (
                    <div
                      key={prop.id}
                      draggable={isManager}
                      onDragStart={isManager ? e => onDragStart(e, prop.id) : undefined}
                      onDragEnd={onDragEnd}
                      className={`bg-white rounded-lg p-3 border shadow-sm transition-all select-none ${
                        isManager ? 'cursor-grab active:cursor-grabbing' : ''
                      } ${isDragging ? 'opacity-40 scale-95' : 'hover:shadow-md'} ${
                        isStuck ? 'border-red-300' : col.cardBorder
                      }`}
                    >
                      {/* Stuck alert banner */}
                      {isStuck && (
                        <div className="flex items-center gap-1 text-red-600 text-xs font-semibold mb-2 bg-red-50 rounded px-2 py-1">
                          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                          <span>Atascada — {days} días sin avanzar</span>
                        </div>
                      )}

                      {/* Title */}
                      <p className="text-sm font-semibold text-slate-900 leading-snug">{prop.title}</p>

                      {/* Reference */}
                      {prop.reference && (
                        <div className="flex items-center gap-1 mt-1">
                          <Tag className="h-3 w-3 text-slate-400" />
                          <span className="text-xs text-slate-500 font-mono">{prop.reference}</span>
                        </div>
                      )}

                      {/* Address */}
                      <p className="text-xs text-slate-400 mt-1 truncate">{prop.address}</p>

                      {/* Price */}
                      <p className="text-sm font-bold text-indigo-600 mt-2">{formatPrice(prop.price)}</p>

                      {/* Footer: agent + days */}
                      <div className="mt-2 flex items-center justify-between">
                        <div className="flex items-center gap-1 min-w-0">
                          <User className="h-3 w-3 text-slate-400 flex-shrink-0" />
                          <span className="text-xs text-slate-500 truncate">
                            {prop.agent_name ?? 'Sin agente'}
                          </span>
                        </div>
                        <div className={`flex items-center gap-1 flex-shrink-0 ${isStuck ? 'text-red-500' : 'text-slate-400'}`}>
                          <Clock className="h-3 w-3" />
                          <span className="text-xs">{days}d</span>
                        </div>
                      </div>
                    </div>
                  );
                })}

                {cards.length === 0 && (
                  <div className="flex items-center justify-center py-8 text-slate-400 text-xs">
                    Sin propiedades
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
