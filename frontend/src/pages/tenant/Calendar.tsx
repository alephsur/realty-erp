import { useEffect, useRef, useState, useCallback } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import listPlugin from '@fullcalendar/list';
import esLocale from '@fullcalendar/core/locales/es';
import type { EventClickArg, DateSelectArg, DatesSetArg, EventDropArg, EventChangeArg } from '@fullcalendar/core';
import { X, Plus, Download, ExternalLink, AlertTriangle, Calendar, Phone, Users, HelpCircle, MapPin, User, Clock } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';

// ─── Types ──────────────────────────────────────────────────────────────────

interface Agent {
  id: string;
  full_name: string;
  role: string;
}

interface CalendarEventData {
  id: string;
  type: 'VISIT' | 'APPOINTMENT';
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  agent_id: string | null;
  agent_name: string | null;
  description?: string | null;
  location?: string | null;
  appointment_type?: string | null;
  visit_status?: string | null;
  property_title?: string | null;
  property_id?: string | null;
  client_name?: string | null;
  client_id?: string | null;
  rating?: number | null;
  feedback?: string | null;
}

interface ConflictWarning {
  type: string;
  id: string;
  title: string;
  start: string;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const AGENT_COLORS = [
  '#6366f1', '#ef4444', '#10b981', '#f59e0b',
  '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6',
  '#f97316', '#84cc16', '#06b6d4', '#a855f7',
];

const APPOINTMENT_TYPE_OPTIONS = [
  { value: 'MEETING', label: 'Reunión', icon: Users },
  { value: 'CALL', label: 'Llamada', icon: Phone },
  { value: 'VISIT', label: 'Visita', icon: Calendar },
  { value: 'OTHER', label: 'Otro', icon: HelpCircle },
];

const APPOINTMENT_TYPE_LABELS: Record<string, string> = {
  MEETING: 'Reunión', CALL: 'Llamada', VISIT: 'Visita', OTHER: 'Otro',
};

const VISIT_STATUS_LABELS: Record<string, string> = {
  SCHEDULED: 'Programada', COMPLETED: 'Completada',
  CANCELLED: 'Cancelada', NO_SHOW: 'No presentado',
};

const VISIT_STATUS_COLORS: Record<string, string> = {
  SCHEDULED: 'bg-blue-100 text-blue-700',
  COMPLETED: 'bg-green-100 text-green-700',
  CANCELLED: 'bg-red-100 text-red-700',
  NO_SHOW: 'bg-slate-100 text-slate-600',
};

function toLocalDatetimeValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function toGoogleCalendarUrl(event: CalendarEventData): string {
  const fmt = (iso: string) => new Date(iso).toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: event.title,
    dates: `${fmt(event.start)}/${fmt(event.end)}`,
    details: event.description || '',
    location: event.location || '',
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const { user } = useAuth();
  const calendarRef = useRef<FullCalendar>(null);
  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';

  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentColorMap, setAgentColorMap] = useState<Record<string, string>>({});
  const [selectedAgentId, setSelectedAgentId] = useState<string>('all');
  const [currentRange, setCurrentRange] = useState<{ start: string; end: string } | null>(null);

  // Modal state
  const [detailEvent, setDetailEvent] = useState<CalendarEventData | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [conflicts, setConflicts] = useState<ConflictWarning[]>([]);

  // Create form
  const [form, setForm] = useState({
    title: '',
    appointment_type: 'MEETING',
    agent_id: '',
    start_at: '',
    end_at: '',
    description: '',
    location: '',
    all_day: false,
  });
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  // Edit mode inside detail modal
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({
    title: '',
    appointment_type: '',
    agent_id: '',
    start_at: '',
    end_at: '',
    description: '',
    location: '',
  });

  // Load agents on mount
  useEffect(() => {
    api.get('/calendar/agents').then(res => {
      const list: Agent[] = res.data.agents;
      setAgents(list);
      const map: Record<string, string> = {};
      list.forEach((a, i) => { map[a.id] = AGENT_COLORS[i % AGENT_COLORS.length]; });
      setAgentColorMap(map);
      if (user && !isManager) {
        setForm(f => ({ ...f, agent_id: user.id }));
      }
    }).catch(() => {});
  }, [isManager, user]);

  // Fetch events when range or agent filter changes
  const [fcEvents, setFcEvents] = useState<object[]>([]);

  const loadEvents = useCallback((start: string, end: string, agentFilter: string, colorMap: Record<string, string>) => {
    const params = new URLSearchParams({ start, end });
    if (agentFilter !== 'all') params.append('agent_id', agentFilter);
    api.get(`/calendar/events?${params}`).then(res => {
      const mapped = (res.data.events as CalendarEventData[]).map(e => ({
        id: e.id,
        title: e.title,
        start: e.start,
        end: e.end,
        allDay: e.all_day,
        backgroundColor: colorMap[e.agent_id ?? ''] || '#94a3b8',
        borderColor: colorMap[e.agent_id ?? ''] || '#94a3b8',
        textColor: '#ffffff',
        editable: e.type === 'APPOINTMENT',
        extendedProps: e,
      }));
      setFcEvents(mapped);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (currentRange && Object.keys(agentColorMap).length > 0) {
      loadEvents(currentRange.start, currentRange.end, selectedAgentId, agentColorMap);
    }
  }, [currentRange, selectedAgentId, agentColorMap, loadEvents]);

  const handleDatesSet = (arg: DatesSetArg) => {
    setCurrentRange({ start: arg.startStr, end: arg.endStr });
  };

  const handleEventClick = (arg: EventClickArg) => {
    const data = arg.event.extendedProps as CalendarEventData;
    setDetailEvent(data);
    setEditMode(false);
    setConflicts([]);
    setEditForm({
      title: data.title,
      appointment_type: data.appointment_type || 'MEETING',
      agent_id: data.agent_id || '',
      start_at: toLocalDatetimeValue(data.start),
      end_at: toLocalDatetimeValue(data.end),
      description: data.description || '',
      location: data.location || '',
    });
  };

  const handleDateSelect = (arg: DateSelectArg) => {
    setForm(f => ({
      ...f,
      start_at: toLocalDatetimeValue(arg.startStr),
      end_at: toLocalDatetimeValue(arg.endStr),
    }));
    setShowCreate(true);
    setConflicts([]);
  };

  const handleEventDrop = (arg: EventDropArg) => {
    const e = arg.event;
    api.put(`/calendar/appointments/${e.id}`, {
      start_at: e.start?.toISOString(),
      end_at: e.end?.toISOString() ?? e.start?.toISOString(),
    }).then(res => {
      if (res.data.conflicts?.length) setConflicts(res.data.conflicts);
      if (currentRange) loadEvents(currentRange.start, currentRange.end, selectedAgentId, agentColorMap);
    }).catch(() => arg.revert());
  };

  const handleEventResize = (arg: EventChangeArg) => {
    const e = arg.event;
    api.put(`/calendar/appointments/${e.id}`, {
      start_at: e.start?.toISOString(),
      end_at: e.end?.toISOString() ?? e.start?.toISOString(),
    }).then(res => {
      if (res.data.conflicts?.length) setConflicts(res.data.conflicts);
      if (currentRange) loadEvents(currentRange.start, currentRange.end, selectedAgentId, agentColorMap);
    }).catch(() => arg.revert());
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title || !form.start_at || !form.end_at) {
      setFormError('Título, inicio y fin son obligatorios.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      const res = await api.post('/calendar/appointments', {
        ...form,
        start_at: new Date(form.start_at).toISOString(),
        end_at: new Date(form.end_at).toISOString(),
        agent_id: form.agent_id || null,
      });
      if (res.data.conflicts?.length) {
        setConflicts(res.data.conflicts);
      }
      setShowCreate(false);
      resetForm();
      if (currentRange) loadEvents(currentRange.start, currentRange.end, selectedAgentId, agentColorMap);
    } catch {
      setFormError('Error al guardar la cita.');
    } finally {
      setSaving(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detailEvent) return;
    setSaving(true);
    try {
      const res = await api.put(`/calendar/appointments/${detailEvent.id}`, {
        ...editForm,
        start_at: new Date(editForm.start_at).toISOString(),
        end_at: new Date(editForm.end_at).toISOString(),
        agent_id: editForm.agent_id || null,
      });
      if (res.data.conflicts?.length) setConflicts(res.data.conflicts);
      setDetailEvent(null);
      setEditMode(false);
      if (currentRange) loadEvents(currentRange.start, currentRange.end, selectedAgentId, agentColorMap);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAppointment = async () => {
    if (!detailEvent) return;
    if (!confirm('¿Eliminar esta cita?')) return;
    await api.delete(`/calendar/appointments/${detailEvent.id}`);
    setDetailEvent(null);
    if (currentRange) loadEvents(currentRange.start, currentRange.end, selectedAgentId, agentColorMap);
  };

  const handleExportIcal = async () => {
    if (!currentRange) return;
    const params = new URLSearchParams({ start: currentRange.start, end: currentRange.end });
    if (selectedAgentId !== 'all') params.append('agent_id', selectedAgentId);
    const res = await api.get(`/calendar/export/ical?${params}`, { responseType: 'blob' });
    const blob = new Blob([res.data], { type: 'text/calendar' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'agenda.ics';
    a.click();
    URL.revokeObjectURL(url);
  };

  const resetForm = () => {
    setForm({ title: '', appointment_type: 'MEETING', agent_id: isManager ? '' : (user?.id || ''), start_at: '', end_at: '', description: '', location: '', all_day: false });
    setFormError('');
    setConflicts([]);
  };

  const openCreate = () => {
    resetForm();
    setShowCreate(true);
  };

  return (
    <div className="flex h-full min-h-screen bg-slate-50">
      {/* ── Sidebar ── */}
      <aside className="hidden w-56 flex-shrink-0 border-r border-slate-200 bg-white p-4 md:flex md:flex-col gap-4">
        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
        >
          <Plus className="h-4 w-4" /> Nueva cita
        </button>

        {isManager && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Agentes</p>
            <ul className="space-y-1">
              <li>
                <button
                  onClick={() => setSelectedAgentId('all')}
                  className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${selectedAgentId === 'all' ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-slate-600 hover:bg-slate-50'}`}
                >
                  <span className="h-2.5 w-2.5 rounded-full bg-slate-400 flex-shrink-0" />
                  Todos
                </button>
              </li>
              {agents.map(a => (
                <li key={a.id}>
                  <button
                    onClick={() => setSelectedAgentId(a.id)}
                    className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${selectedAgentId === a.id ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-slate-600 hover:bg-slate-50'}`}
                  >
                    <span
                      className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: agentColorMap[a.id] || '#94a3b8' }}
                    />
                    <span className="truncate">{a.full_name}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {conflicts.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
              <p className="text-xs font-semibold text-amber-700">Conflictos</p>
            </div>
            {conflicts.map(c => (
              <p key={c.id} className="text-xs text-amber-600 truncate">{c.title}</p>
            ))}
          </div>
        )}

        <div className="mt-auto">
          <button
            onClick={handleExportIcal}
            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <Download className="h-4 w-4" /> Exportar .ics
          </button>
        </div>
      </aside>

      {/* ── Main Calendar ── */}
      <div className="flex-1 p-4 md:p-6 min-w-0">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-900">Calendario</h1>
          <div className="flex gap-2 md:hidden">
            <button onClick={openCreate} className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white">
              <Plus className="h-4 w-4" /> Nueva cita
            </button>
            <button onClick={handleExportIcal} className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600">
              <Download className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <FullCalendar
            ref={calendarRef}
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin, listPlugin]}
            initialView="timeGridWeek"
            locale={esLocale}
            firstDay={1}
            headerToolbar={{
              left: 'prev,next today',
              center: 'title',
              right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
            }}
            buttonText={{ today: 'Hoy', month: 'Mes', week: 'Semana', day: 'Día', list: 'Lista' }}
            height="auto"
            contentHeight={620}
            events={fcEvents}
            selectable
            selectMirror
            editable
            eventDurationEditable
            slotMinTime="07:00:00"
            slotMaxTime="21:00:00"
            allDaySlot
            nowIndicator
            datesSet={handleDatesSet}
            eventClick={handleEventClick}
            select={handleDateSelect}
            eventDrop={handleEventDrop}
            eventChange={handleEventResize}
            eventTimeFormat={{ hour: '2-digit', minute: '2-digit', hour12: false }}
            slotLabelFormat={{ hour: '2-digit', minute: '2-digit', hour12: false }}
          />
        </div>

        {/* Agent legend — mobile */}
        {isManager && agents.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2 md:hidden">
            {agents.map(a => (
              <button
                key={a.id}
                onClick={() => setSelectedAgentId(selectedAgentId === a.id ? 'all' : a.id)}
                className="flex items-center gap-1.5 rounded-full border border-slate-200 px-2 py-1 text-xs text-slate-600"
              >
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: agentColorMap[a.id] }} />
                {a.full_name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Detail Modal ── */}
      {detailEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => { setDetailEvent(null); setEditMode(false); }}>
          <div className="w-full max-w-md rounded-xl bg-white shadow-xl" onClick={e => e.stopPropagation()}>
            <div
              className="flex items-center justify-between rounded-t-xl px-5 py-4"
              style={{ backgroundColor: agentColorMap[detailEvent.agent_id ?? ''] || '#94a3b8' }}
            >
              <div className="flex-1 min-w-0 pr-2">
                {!editMode ? (
                  <h2 className="text-base font-semibold text-white truncate">{detailEvent.title}</h2>
                ) : null}
                <span className="inline-block mt-1 rounded-full bg-white/20 px-2 py-0.5 text-xs text-white font-medium">
                  {detailEvent.type === 'VISIT'
                    ? 'Visita a propiedad'
                    : APPOINTMENT_TYPE_LABELS[detailEvent.appointment_type ?? ''] ?? 'Cita'}
                </span>
              </div>
              <button onClick={() => { setDetailEvent(null); setEditMode(false); }} className="rounded-full p-1 text-white/80 hover:bg-white/20">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-5 space-y-3">
              {!editMode ? (
                <>
                  <DetailRow icon={<Clock className="h-4 w-4" />} label={
                    `${new Date(detailEvent.start).toLocaleString('es-ES', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })} → ${new Date(detailEvent.end).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`
                  } />
                  {detailEvent.agent_name && (
                    <DetailRow icon={<User className="h-4 w-4" />} label={detailEvent.agent_name} />
                  )}
                  {detailEvent.location && (
                    <DetailRow icon={<MapPin className="h-4 w-4" />} label={detailEvent.location} />
                  )}
                  {detailEvent.description && (
                    <p className="text-sm text-slate-600 bg-slate-50 rounded-lg p-3">{detailEvent.description}</p>
                  )}
                  {detailEvent.type === 'VISIT' && (
                    <>
                      {detailEvent.client_name && (
                        <DetailRow icon={<User className="h-4 w-4" />} label={`Cliente: ${detailEvent.client_name}`} />
                      )}
                      {detailEvent.visit_status && (
                        <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${VISIT_STATUS_COLORS[detailEvent.visit_status]}`}>
                          {VISIT_STATUS_LABELS[detailEvent.visit_status]}
                        </span>
                      )}
                    </>
                  )}

                  <div className="flex flex-wrap gap-2 pt-2">
                    <a
                      href={toGoogleCalendarUrl(detailEvent)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      <ExternalLink className="h-3.5 w-3.5" /> Google Calendar
                    </a>
                    <button
                      onClick={async () => {
                        const params = new URLSearchParams({
                          start: detailEvent.start,
                          end: detailEvent.end,
                        });
                        if (detailEvent.agent_id) params.append('agent_id', detailEvent.agent_id);
                        const res = await api.get(`/calendar/export/ical?${params}`, { responseType: 'blob' });
                        const blob = new Blob([res.data], { type: 'text/calendar' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'evento.ics';
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                      className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      <Download className="h-3.5 w-3.5" /> Exportar .ics
                    </button>
                    {detailEvent.type === 'APPOINTMENT' && (
                      <>
                        <button onClick={() => setEditMode(true)} className="flex items-center gap-1.5 rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100">
                          Editar
                        </button>
                        <button onClick={handleDeleteAppointment} className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-100">
                          Eliminar
                        </button>
                      </>
                    )}
                  </div>
                </>
              ) : (
                <form onSubmit={handleEditSubmit} className="space-y-3">
                  <AppointmentFormFields
                    form={editForm}
                    setForm={setEditForm as React.Dispatch<React.SetStateAction<typeof editForm>>}
                    agents={agents}
                    isManager={isManager}
                    userId={user?.id || ''}
                  />
                  <div className="flex gap-2 pt-1">
                    <button type="submit" disabled={saving} className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
                      {saving ? 'Guardando...' : 'Guardar'}
                    </button>
                    <button type="button" onClick={() => setEditMode(false)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">
                      Cancelar
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Create Modal ── */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => { setShowCreate(false); resetForm(); }}>
          <div className="w-full max-w-md rounded-xl bg-white shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 className="text-base font-semibold text-slate-900">Nueva cita</h2>
              <button onClick={() => { setShowCreate(false); resetForm(); }} className="rounded-full p-1 text-slate-400 hover:bg-slate-100">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreateSubmit} className="p-5 space-y-3">
              <AppointmentFormFields
                form={form}
                setForm={setForm as React.Dispatch<React.SetStateAction<typeof form>>}
                agents={agents}
                isManager={isManager}
                userId={user?.id || ''}
              />
              {formError && (
                <p className="text-sm text-red-600 flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4" /> {formError}
                </p>
              )}
              {conflicts.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-semibold text-amber-700 mb-1 flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5" /> Conflictos detectados</p>
                  {conflicts.map(c => (
                    <p key={c.id} className="text-xs text-amber-600">{c.title} — {new Date(c.start).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</p>
                  ))}
                </div>
              )}
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={saving} className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
                  {saving ? 'Guardando...' : 'Crear cita'}
                </button>
                <button type="button" onClick={() => { setShowCreate(false); resetForm(); }} className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function DetailRow({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-start gap-2 text-sm text-slate-600">
      <span className="mt-0.5 text-slate-400 flex-shrink-0">{icon}</span>
      <span>{label}</span>
    </div>
  );
}

interface FormFieldsProps {
  form: {
    title: string;
    appointment_type: string;
    agent_id: string;
    start_at: string;
    end_at: string;
    description: string;
    location: string;
    all_day?: boolean;
  };
  setForm: React.Dispatch<React.SetStateAction<FormFieldsProps['form']>>;
  agents: Agent[];
  isManager: boolean;
  userId: string;
}

function AppointmentFormFields({ form, setForm, agents, isManager }: FormFieldsProps) {
  const set = (k: string, v: string | boolean) => setForm((f: FormFieldsProps['form']) => ({ ...f, [k]: v }));

  return (
    <>
      <div>
        <label className="block text-xs font-medium text-slate-700 mb-1">Título *</label>
        <input
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          value={form.title}
          onChange={e => set('title', e.target.value)}
          placeholder="Nombre de la cita"
          required
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-700 mb-1">Tipo</label>
        <div className="grid grid-cols-4 gap-1">
          {APPOINTMENT_TYPE_OPTIONS.map(opt => {
            const Icon = opt.icon;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => set('appointment_type', opt.value)}
                className={`flex flex-col items-center gap-1 rounded-lg border py-2 text-xs font-medium transition-colors ${form.appointment_type === opt.value ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}
              >
                <Icon className="h-4 w-4" />
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {isManager && (
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Agente</label>
          <select
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.agent_id}
            onChange={e => set('agent_id', e.target.value)}
          >
            <option value="">Sin asignar</option>
            {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
          </select>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Inicio *</label>
          <input
            type="datetime-local"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.start_at}
            onChange={e => set('start_at', e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Fin *</label>
          <input
            type="datetime-local"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.end_at}
            onChange={e => set('end_at', e.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-700 mb-1">Ubicación</label>
        <input
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          value={form.location}
          onChange={e => set('location', e.target.value)}
          placeholder="Oficina, dirección..."
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-700 mb-1">Descripción</label>
        <textarea
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
          rows={2}
          value={form.description}
          onChange={e => set('description', e.target.value)}
          placeholder="Notas adicionales..."
        />
      </div>
    </>
  );
}
