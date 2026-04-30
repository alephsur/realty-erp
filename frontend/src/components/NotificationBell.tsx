import { useState, useEffect, useRef } from 'react';
import { Bell, Check, CheckCheck, Home, Users, DollarSign, CalendarDays } from 'lucide-react';
import client from '../api/client';

interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  read_at: string | null;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string | null;
  is_read: boolean;
}

const TYPE_ICON: Record<string, React.ElementType> = {
  MATCH_FOUND: Users,
  SALE_REGISTERED: DollarSign,
  VISIT_SCHEDULED: CalendarDays,
};

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'Ahora';
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  const fetchCount = async () => {
    try {
      const res = await client.get('/notifications/unread-count');
      setUnread(res.data.count);
    } catch { /* ignore */ }
  };

  const fetchNotifications = async () => {
    try {
      const res = await client.get('/notifications', { params: { limit: 20 } });
      setNotifications(res.data);
      setUnread(res.data.filter((n: Notification) => !n.is_read).length);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchCount();
    const interval = setInterval(fetchCount, 30_000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markRead = async (id: string) => {
    try {
      await client.put(`/notifications/${id}/read`);
      setNotifications(ns => ns.map(n => n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n));
      setUnread(c => Math.max(0, c - 1));
    } catch { /* ignore */ }
  };

  const markAllRead = async () => {
    try {
      await client.post('/notifications/read-all');
      setNotifications(ns => ns.map(n => ({ ...n, is_read: true, read_at: new Date().toISOString() })));
      setUnread(0);
    } catch { /* ignore */ }
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="relative flex items-center justify-center w-9 h-9 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
        aria-label="Notificaciones"
      >
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 flex items-center justify-center rounded-full bg-indigo-600 text-white text-[10px] font-bold leading-none">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 w-80 bg-white rounded-xl shadow-xl ring-1 ring-slate-900/10 z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <span className="text-sm font-semibold text-slate-900">Notificaciones</span>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                Marcar todas leídas
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto divide-y divide-slate-50">
            {notifications.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <Bell className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-400">Sin notificaciones</p>
              </div>
            ) : (
              notifications.map(n => {
                const Icon = TYPE_ICON[n.type] || Home;
                return (
                  <div
                    key={n.id}
                    className={`flex gap-3 px-4 py-3 hover:bg-slate-50 transition-colors ${!n.is_read ? 'bg-indigo-50/40' : ''}`}
                  >
                    <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mt-0.5 ${
                      !n.is_read ? 'bg-indigo-100' : 'bg-slate-100'
                    }`}>
                      <Icon className={`w-4 h-4 ${!n.is_read ? 'text-indigo-600' : 'text-slate-500'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs font-semibold truncate ${!n.is_read ? 'text-slate-900' : 'text-slate-600'}`}>
                        {n.title}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.body}</p>
                      <p className="text-[10px] text-slate-400 mt-1">{timeAgo(n.created_at)}</p>
                    </div>
                    {!n.is_read && (
                      <button
                        onClick={() => markRead(n.id)}
                        className="flex-shrink-0 mt-1 text-indigo-400 hover:text-indigo-600"
                        title="Marcar como leída"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
