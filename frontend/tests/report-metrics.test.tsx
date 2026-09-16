import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import client from '../src/api/client';
import ReportMetrics, { ReportPeriodNote } from '../src/components/ReportMetrics';
import Reports from '../src/pages/tenant/Reports';

vi.mock('../src/api/client', () => ({ default: { get: vi.fn() } }));
const metrics = {
  period_start: '2026-03-01T00:00:00Z', period_end: '2026-03-15T12:00:00Z',
  comparison_start: '2026-02-01T00:00:00Z', comparison_end: '2026-02-15T12:00:00Z',
  completed_visits: 2, no_show_visits: 1, unresolved_visits: 3,
  attendance_denominator: 3, visit_attendance_rate: 66.7,
  visited_buyer_property_pairs: 2, closed_buyer_property_pairs: 1, visit_to_close_rate: 50,
  completed_visits_without_buyer: 1, visit_to_offer_rate: null, offer_to_close_rate: null,
  offer_metrics_unavailable_reason: 'Todavía no se registran ofertas vinculadas a visitas y cierres.',
};
const kpi = { ...metrics, period: 'this_month', sales_count: 1, sales_volume: 200000,
  sales_count_change: null, sales_volume_change: null, agency_commission: 3600,
  agency_commission_change: null, agent_commission_total: 2400, avg_ticket: 200000, avg_commission_pct: 3,
  total_properties: 4, active_properties: 3, unassigned_properties: 0, total_clients: 2, total_agents: 1,
  sold_portfolio_share: 25 };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(client.get).mockImplementation(async url => ({ data: url.includes('kpi-summary') ? kpi : [] }));
});
afterEach(cleanup);

test('attendance, close conversion and unavailable offer metrics are distinct', () => {
  render(<ReportMetrics metrics={metrics} />);
  const attendance = screen.getByRole('heading', { name: 'Asistencia a visitas' }).closest('article')!;
  expect(within(attendance).getByText('66.7%')).toBeTruthy();
  expect(within(attendance).getByText(/2 realizadas de 3/)).toBeTruthy();
  const conversion = screen.getByRole('heading', { name: 'Visita → cierre' }).closest('article')!;
  expect(within(conversion).getByText('50.0%')).toBeTruthy();
  expect(within(conversion).getByText(/1 de 2 pares/)).toBeTruthy();
  expect(screen.getAllByText('No disponible')).toHaveLength(2);
});

test('missing observations differ from an observed zero percent', () => {
  const { rerender } = render(<ReportMetrics metrics={{ ...metrics, visit_attendance_rate: null, visit_to_close_rate: null }} />);
  expect(screen.getAllByText('Sin observaciones')).toHaveLength(2);
  rerender(<ReportMetrics metrics={{ ...metrics, visit_attendance_rate: 0, visit_to_close_rate: 0 }} />);
  expect(screen.getAllByText('0.0%')).toHaveLength(2);
});

test('period notes distinguish activity, comparison and current portfolio', () => {
  const { rerender } = render(<ReportPeriodNote metrics={metrics} />);
  expect(screen.getByText(/Periodo de actividad \(UTC\)/)).toBeTruthy();
  expect(screen.getByText(/mismo tiempo transcurrido/)).toBeTruthy();
  expect(screen.getByText(/situación actual/)).toBeTruthy();
  rerender(<ReportPeriodNote metrics={{ ...metrics, period_start: null, comparison_start: null, comparison_end: null }} />);
  expect(screen.getByText(/Desde el primer registro/)).toBeTruthy();
  expect(screen.getByText(/no tiene comparación/)).toBeTruthy();
});

test('report visit and client charts use counts instead of currency', async () => {
  vi.mocked(client.get).mockImplementation(async url => ({ data:
    url.includes('kpi-summary') ? kpi : url.includes('visit-analytics') ? [{ period: '2026-03', COMPLETED: 2, SCHEDULED: 3, CANCELLED: 1, NO_SHOW: 1 }]
      : url.includes('client-acquisition') ? [{ period: '2026-03', Propietario: 2, Demandante: 3 }] : [] }));
  render(<Reports />);
  await screen.findByText('Reportes y Analíticas');
  const titles = Array.from(document.querySelectorAll('svg title')).map(el => el.textContent);
  expect(titles).toContain('2026-03 — Realizadas: 2 visitas');
  expect(titles).toContain('2026-03: 2 clientes');
  expect(titles.every(title => !title?.includes('€'))).toBe(true);
  expect(screen.getByText('Cartera por estado')).toBeTruthy();
  expect(screen.queryByText('Conv. portfolio')).toBeNull();
});

test('a failed period change shows an error instead of old figures', async () => {
  render(<Reports />);
  const selector = await screen.findByLabelText('Periodo de actividad');
  vi.mocked(client.get).mockRejectedValue(new Error('Disconnected'));
  fireEvent.change(selector, { target: { value: 'last_month' } });
  expect((await screen.findByRole('alert')).textContent).toContain('No se pudieron cargar');
  expect(screen.queryByText('200.000 €')).toBeNull();
  vi.mocked(client.get).mockImplementation(async url => ({ data: url.includes('kpi-summary') ? { ...kpi, period: 'last_month', sales_count: 7 } : [] }));
  fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  expect(await screen.findByLabelText('Periodo de actividad')).toBeTruthy();
});
