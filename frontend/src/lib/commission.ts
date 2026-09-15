// Integer arithmetic keeps the preview consistent with the backend's HALF_UP rule.
function scaled(value: string, places: number): bigint | null {
  if (!new RegExp(`^\\d+(?:\\.\\d{1,${places}})?$`).test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * 10n ** BigInt(places) + BigInt(fraction.padEnd(places, '0'));
}

export function previewCommission(price: string, rate: string, agentRate: string) {
  const cents = scaled(price, 2);
  const commission = scaled(rate, 4);
  const share = scaled(agentRate, 4);
  if (cents === null || cents <= 0n || cents > 9999999999999999n ||
      commission === null || commission > 1000000n || share === null || share > 1000000n) return null;
  const total = (cents * commission + 500000n) / 1000000n;
  const agent = (total * share + 500000n) / 1000000n;
  return { total, agent, agency: total - agent };
}

export function formatCents(cents: bigint): string {
  return `${(cents / 100n).toLocaleString('es-ES')},${(cents % 100n).toString().padStart(2, '0')} €`;
}
