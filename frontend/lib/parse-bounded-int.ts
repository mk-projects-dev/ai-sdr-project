/** Max digits for daily cap (2000) and delay minutes (1440). */
export const THROTTLE_INT_MAX_DIGITS = 4;

/** Keeps only ASCII digits and caps length so pasted junk cannot flood the field. */
export function sanitizeUnsignedDigits(
  raw: string,
  maxDigits = THROTTLE_INT_MAX_DIGITS,
): string {
  return raw.replace(/\D/g, "").slice(0, maxDigits);
}

/** Parses integer user input; returns null if empty, non-numeric, or outside [min, max]. */
export function parseBoundedInt(
  raw: string,
  min: number,
  max: number,
): number | null {
  const s = raw.trim();
  if (!s) return null;
  const n = Number(s);
  if (!Number.isFinite(n)) return null;
  const i = Math.floor(n);
  if (i < min || i > max) return null;
  return i;
}
