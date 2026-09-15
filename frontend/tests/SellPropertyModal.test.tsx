import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import client from '../src/api/client';
import SellPropertyModal from '../src/components/SellPropertyModal';

vi.mock('../src/api/client', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const options = {
  property: { title: 'Casa de prueba', price: 200000, status_key: 'CAPTADA',
    agent_id: 'agent', commission_rate: 3, agent_commission_rate: null },
  agents: [{ id: 'agent', full_name: 'Agente asignado', commission_rate: 40 },
    { id: 'second', full_name: 'Segundo agente', commission_rate: 60 }],
  buyers: [{ id: 'buyer', full_name: 'Compradora de prueba' }], pages: 1, total: 1,
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(client.get).mockResolvedValue({ data: structuredClone(options) });
  vi.mocked(client.post).mockResolvedValue({ data: { sale_id: 'sale' } });
});
afterEach(cleanup);

async function form() {
  const onClose = vi.fn();
  const onSold = vi.fn();
  render(<SellPropertyModal propertyId="property" onClose={onClose} onSold={onSold} />);
  await screen.findByRole('option', { name: 'Compradora de prueba' });
  fireEvent.change(screen.getByLabelText('Comprador *'), { target: { value: 'buyer' } });
  return { onClose, onSold, confirm: screen.getByRole('button', { name: 'Confirmar venta' }) as HTMLButtonElement };
}

test('cancel leaves the sale untouched', async () => {
  const { onClose, onSold } = await form();
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
  expect(onClose).toHaveBeenCalledOnce();
  expect(onSold).not.toHaveBeenCalled();
  expect(client.post).not.toHaveBeenCalled();
});

test.each(['Comprador *', 'Precio final (€) *', 'Agente de la venta *', 'Comisión sobre la venta (%) *', 'Parte del agente (%) *'])('requires %s', async label => {
  const { confirm } = await form();
  fireEvent.change(screen.getByLabelText(label), { target: { value: '' } });
  expect(confirm.disabled).toBe(true);
  fireEvent.submit(confirm.closest('form')!);
  expect(client.post).not.toHaveBeenCalled();
});

test('submits explicit closing data and shows the exact split', async () => {
  const { confirm, onSold } = await form();
  fireEvent.change(screen.getByLabelText('Precio final (€) *'), { target: { value: '100.50' } });
  fireEvent.change(screen.getByLabelText('Comisión sobre la venta (%) *'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Parte del agente (%) *'), { target: { value: '50' } });
  expect(screen.getByText('1,01 €')).toBeTruthy();
  expect(screen.getByText('0,51 €')).toBeTruthy();
  expect(screen.getByText('0,50 €')).toBeTruthy();
  fireEvent.click(confirm);
  await waitFor(() => expect(onSold).toHaveBeenCalledOnce());
  expect(client.post).toHaveBeenCalledWith('/properties/property/sell', {
    buyer_id: 'buyer', agent_id: 'agent', sale_price: '100.50', commission_rate: '1',
    agent_commission_rate: '50', notes: null, request_id: expect.any(String),
  });
});

test('blocks duplicate submission while the first request is pending', async () => {
  let finish!: (value: { data: { sale_id: string } }) => void;
  vi.mocked(client.post).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const { confirm, onSold } = await form();
  fireEvent.submit(confirm.closest('form')!);
  fireEvent.submit(confirm.closest('form')!);
  expect(client.post).toHaveBeenCalledOnce();
  expect(confirm.disabled).toBe(true);
  await act(async () => finish({ data: { sale_id: 'sale' } }));
  expect(onSold).toHaveBeenCalledOnce();
});

test('a retry after a lost response reuses the request id', async () => {
  vi.mocked(client.post).mockRejectedValueOnce(new Error('Network failure'));
  const { confirm, onSold } = await form();
  fireEvent.click(confirm);
  await screen.findByRole('alert');
  expect(onSold).not.toHaveBeenCalled();
  fireEvent.click(confirm);
  await waitFor(() => expect(onSold).toHaveBeenCalledOnce());
  const calls = vi.mocked(client.post).mock.calls;
  expect(calls[0][1]).toEqual(calls[1][1]);
});

test('retains the form and explains a conflicting closure', async () => {
  vi.mocked(client.post).mockRejectedValueOnce({ isAxiosError: true,
    response: { data: { detail: 'La propiedad ya tiene un cierre.' } } });
  const { confirm, onSold } = await form();
  fireEvent.click(confirm);
  expect((await screen.findByRole('alert')).textContent).toContain('La propiedad ya tiene un cierre.');
  expect(onSold).not.toHaveBeenCalled();
  expect((screen.getByLabelText('Comprador *') as HTMLSelectElement).value).toBe('buyer');
});

test('uses the selected agent rate instead of the previously assigned agent rate', async () => {
  await form();
  fireEvent.change(screen.getByLabelText('Agente de la venta *'), { target: { value: 'second' } });
  expect((screen.getByLabelText('Parte del agente (%) *') as HTMLInputElement).value).toBe('60');
});

test('missing legacy rates remain blank and cannot silently become zero', async () => {
  vi.mocked(client.get).mockResolvedValue({ data: { ...options,
    property: { ...options.property, commission_rate: null } } });
  const { confirm } = await form();
  expect((screen.getByLabelText('Comisión sobre la venta (%) *') as HTMLInputElement).value).toBe('');
  expect(confirm.disabled).toBe(true);
});
