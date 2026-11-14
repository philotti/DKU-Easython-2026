export const API = 'http://127.0.0.1:8000';
export async function apiGet(path, signal) {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
}
export function filterExamples(items, f) {
  const query = (f.q ?? '').trim().toLowerCase();
  return items.filter((a) => a.comparison_type === f.comparison_type
    && (!query || ['item_name', 'model', 'agency_name'].some((key) => String(a.target[key] ?? '').toLowerCase().includes(query)))
    && (!f.agency_id || a.target.agency_id === f.agency_id)
    && (!f.item_id || a.target.item_id === f.item_id) && (!f.status || a.status === f.status))
    .sort((a, b) => {
      if (f.sort === 'difference_pct_desc') {
        const x = a.difference_pct, y = b.difference_pct;
        return x == null ? (y == null ? a.record_id.localeCompare(b.record_id) : 1) : y == null ? -1 : Number(y) - Number(x) || a.record_id.localeCompare(b.record_id);
      }
      return String(b.target.purchased_at ?? '').localeCompare(String(a.target.purchased_at ?? '')) || a.record_id.localeCompare(b.record_id);
    });
}
