// Backend stores timestamps as UTC ISO strings. Render them in the viewer's
// local timezone as "YYYY-MM-DD HH:mm" (slicing the raw ISO showed UTC as if
// it were local time).
export function fmtLocal(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso; // not a parseable date — show verbatim
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
    + `${p(d.getHours())}:${p(d.getMinutes())}`;
}
