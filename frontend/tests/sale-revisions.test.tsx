import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import client from '../src/api/client';
import SellPropertyModal from '../src/components/SellPropertyModal';
import SaleHistoryModal from '../src/components/SaleHistoryModal';
import Commissions from '../src/pages/tenant/Commissions';

vi.mock('../src/api/client', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const sale = { id: 'sale', property_id: 'property', version: 2, is_active: true,
  buyer_id: 'buyer', buyer_name: 'Compradora', agent_id: 'agent', sale_price: '200000.01',
  commission_rate: '3', agent_commission_rate: '40', agent_commission: '2400',
  sale_date: '2026-09-01T10:20:00Z', notes: 'Condiciones originales' };
const options = { property: { title: 'Casa', price: 300000, status_key: 'VENDIDA', agent_id: 'agent', commission_rate: 4 },
  buyers: [{ id: 'buyer', full_name: 'Compradora' }], agents: [{ id: 'agent', full_name: 'Agente', commission_rate: 50 }], pages: 1, total: 1 };
const detail = { sale, events: [{ id: 'event', kind: 'CORRECTED', version: 2, actor_name: 'Gerente', reason: 'Ajuste del precio',
  created_at: '2026-09-02T12:00:00Z', before: { sale_price: '250000' }, after: { sale_price: '200000.01' } }],
  commissions: [{ id: 'credit', agent_name: 'Agente', amount: '-600', kind: 'ADJUSTMENT', status: 'PENDING', invoice_number: null, payment_date: null }] };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(client.get).mockImplementation(async url => ({ data: url.includes('closing-options') ? options : detail }));
  vi.mocked(client.post).mockResolvedValue({ data: {} });
});
afterEach(cleanup);

test('correction uses sale values, requires a reason and sends versioned data', async () => {
  const saved = vi.fn();
  render(<SellPropertyModal propertyId="property" revision={sale} onClose={vi.fn()} onSold={saved} />);
  await screen.findByText('Casa');
  await waitFor(() => expect((screen.getByLabelText('Precio final (€) *') as HTMLInputElement).value).toBe('200000.01'));
  expect((screen.getByLabelText('Parte del agente (%) *') as HTMLInputElement).value).toBe('40');
  const confirm = screen.getByRole('button', { name: 'Guardar corrección' }) as HTMLButtonElement;
  expect(confirm.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Motivo de la corrección *'), { target: { value: 'Precio definitivo' } });
  fireEvent.change(screen.getByLabelText('Precio final (€) *'), { target: { value: '150000' } });
  fireEvent.click(confirm);
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  expect(client.post).toHaveBeenCalledWith('/sales/sale/correct', expect.objectContaining({
    expected_version: 2, reason: 'Precio definitivo', sale_price: '150000', buyer_id: 'buyer', agent_id: 'agent',
    sale_date: '2026-09-01T10:20:00.000Z', request_id: expect.any(String),
  }));
});

test('a stale correction keeps the entered values and explains the conflict', async () => {
  vi.mocked(client.post).mockRejectedValue({ isAxiosError: true, response: { data: { detail: 'La venta ha cambiado. Vuelve a cargarla.' } } });
  render(<SellPropertyModal propertyId="property" revision={sale} onClose={vi.fn()} onSold={vi.fn()} />);
  await screen.findByText('Casa');
  fireEvent.change(screen.getByLabelText('Motivo de la corrección *'), { target: { value: 'Corregir' } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar corrección' }));
  expect((await screen.findByRole('alert')).textContent).toContain('La venta ha cambiado');
  expect((screen.getByLabelText('Motivo de la corrección *') as HTMLTextAreaElement).value).toBe('Corregir');
});

test('history shows who changed the sale and the signed commission adjustment', async () => {
  render(<SaleHistoryModal saleId="sale" onClose={vi.fn()} onChanged={vi.fn()} />);
  expect(await screen.findByText('Ajuste del precio')).toBeTruthy();
  expect(screen.getByText(/Gerente/)).toBeTruthy();
  expect(screen.getByText('250000')).toBeTruthy();
  expect(screen.getByText(/-600/)).toBeTruthy();
});

test('reopening requires a reason, retries safely and refreshes history', async () => {
  const changed = vi.fn();
  vi.mocked(client.post).mockRejectedValueOnce(new Error('Lost response'));
  render(<SaleHistoryModal saleId="sale" onClose={vi.fn()} onChanged={changed} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Reabrir venta' }));
  const confirm = screen.getByRole('button', { name: 'Confirmar reapertura' }) as HTMLButtonElement;
  expect(confirm.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Motivo de la reapertura'), { target: { value: 'Comprador desiste' } });
  fireEvent.change(screen.getByLabelText('Estado tras reabrir'), { target: { value: 'RETIRADA' } });
  fireEvent.click(confirm);
  await screen.findByRole('alert');
  fireEvent.click(confirm);
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  const calls = vi.mocked(client.post).mock.calls;
  expect(calls[0]).toEqual(calls[1]);
  expect(calls[0]).toEqual(['/sales/sale/reopen', expect.objectContaining({ expected_version: 2, target_status: 'RETIRADA', reason: 'Comprador desiste' })]);
});

test('reopened history explains the inactive sale and prevents another correction', async () => {
  vi.mocked(client.get).mockResolvedValue({ data: { ...detail, sale: { ...sale, is_active: false } } });
  render(<SaleHistoryModal saleId="sale" onClose={vi.fn()} onChanged={vi.fn()} />);
  await screen.findByText(/sin efecto en los indicadores/);
  expect(screen.queryByRole('button', { name: 'Corregir venta' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Reabrir venta' })).toBeNull();
});

function mockCommissions(balance: number) {
  const cp = { id: 'entry', sale_id: 'sale', agent_id: 'agent', agent_name: 'Agente', amount: balance,
    kind: 'ADJUSTMENT', status: 'PENDING', payment_date: null, invoice_number: null, notes: null,
    created_at: '2026-09-15', property_title: 'Casa', property_reference: 'REF', sale_price: 200000, sale_date: '2026-09-01' };
  vi.mocked(client.get).mockImplementation(async url => ({ data:
    url === '/commissions/pending' ? [{ agent_id: 'agent', agent_name: 'Agente', total_pending: balance, balance_token: 'token', commissions: [cp] }]
      : url === '/commissions/summary' ? { total: balance, pending: balance, invoiced: 0, paid: 0, count_total: 1, count_pending: 1, count_invoiced: 0, count_paid: 0 }
        : url === '/commissions/history' ? { items: [], pages: 1, total: 0 } : [] }));
}

test.each([
  [1200, 'Liquidar saldo', 'Confirmar pago'],
  [-600, 'Registrar devolución', 'Confirmar devolución'],
  [0, 'Compensar saldo', 'Confirmar compensación'],
])('settles the full agent balance of %s with a balance token', async (balance, action, confirm) => {
  mockCommissions(Number(balance));
  render(<Commissions />);
  fireEvent.click(await screen.findByRole('button', { name: String(action) }));
  fireEvent.click(screen.getByRole('button', { name: String(confirm) }));
  await waitFor(() => expect(client.post).toHaveBeenCalledOnce());
  expect(client.post).toHaveBeenCalledWith('/commissions/agents/agent/settle', expect.objectContaining({ balance_token: 'token', request_id: expect.any(String) }));
});

test('invoicing selects the exact adjustment entry', async () => {
  mockCommissions(-600);
  render(<Commissions />);
  fireEvent.click(await screen.findByRole('button', { name: 'Facturar' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmar factura' }));
  await waitFor(() => expect(client.post).toHaveBeenCalledWith('/commissions/entries/entry/invoice', expect.any(Object)));
  expect(within(document.body).queryByRole('button', { name: 'Pagar' })).toBeNull();
});

test('history directs settlement to the full pending balance', async () => {
  mockCommissions(1200);
  const get = vi.mocked(client.get).getMockImplementation()!;
  vi.mocked(client.get).mockImplementation(async (url, config) => url === '/commissions/history'
    ? { data: { items: [{ id: 'entry', sale_id: 'sale', agent_id: 'agent', agent_name: 'Agente', amount: 1200,
      kind: 'ADJUSTMENT', status: 'PENDING', property_title: 'Casa', sale_date: '2026-09-01' }], total: 1, pages: 1 } }
    : get(url, config));
  render(<Commissions />);
  await screen.findByRole('button', { name: 'Liquidar saldo' });
  fireEvent.click(screen.getByRole('button', { name: 'Historial' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Ver saldo' }));
  expect(await screen.findByRole('button', { name: 'Liquidar saldo' })).toBeTruthy();
  expect(client.post).not.toHaveBeenCalled();
});
