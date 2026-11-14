export const SIDES = [6, 12, 24, 48, 96] as const;
export type Bound = 'lower' | 'upper';
export const PI_COLORS = { lower: '#1769ed', upper: '#ee852e', circle: '#536074' };

export function bounds(n: number) {
  // Start with a unit-radius hexagon. Half-angle geometry uses no known pi value.
  let count = 6, side = 1;
  while (count < n) {
    const apothem = Math.sqrt(1 - side * side / 4);
    side = side / Math.sqrt(2 + 2 * apothem);
    count *= 2;
  }
  if (count !== n) throw new Error('边数必须从6开始连续翻倍');
  return { lower: n * side / 2, upper: n * side / (2 * Math.sqrt(1 - side * side / 4)) };
}

// Outward rounding preserves the guarantee when displaying a finite decimal.
export function displayedBounds(n: number, digits = 4) {
  const b = bounds(n), scale = 10 ** digits;
  return {
    lower: (Math.floor(b.lower * scale) / scale).toFixed(digits),
    upper: (Math.ceil(b.upper * scale) / scale).toFixed(digits),
  };
}

export function commonPrefix(n: number) {
  const { lower, upper } = displayedBounds(n);
  let i = 0;
  while (i < lower.length && lower[i] === upper[i]) i++;
  return lower.slice(0, i).replace(/\.$/, '');
}

export function polygonPoints(n: number, outer = false, cx = 180, cy = 180, radius = 132) {
  const r = outer ? radius / Math.cos(Math.PI / n) : radius;
  return Array.from({ length: n }, (_, i) => {
    const angle = 2 * Math.PI * i / n;
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
  }).join(' ');
}
