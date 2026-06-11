const BASE  = import.meta.env.VITE_API_URL  || 'http://localhost:3001';
const AGENT = import.meta.env.VITE_AGENT_URL || 'http://172.25.29.253:8000';

async function get(path, params = {}) {
  const url = new URL(BASE + path);
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== '' && url.searchParams.set(k, v));
  const r = await fetch(url);
  return r.json();
}

export const api = {
  incidents: (params) => get('/incidents', params),
  incident: (id) => get(`/incidents/${id}`),
  stats: () => get('/stats'),
  filters: () => get('/filters'),
  liveProblems: () => get('/live-problems'),
  health: () => get('/health'),
  approvals: (status) => get('/approvals', status ? { status } : {}),
  approval: (id) => get(`/approvals/${id}`),
  decide: (id, status, decided_by, decision_note) => {
    return fetch(`${BASE}/approvals/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, decided_by, decision_note }),
    }).then(r => r.json());
  },
  chat: (question, context = {}) =>
    fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, context }),
    }).then(r => r.json()),
  checkCreds: () => get('/health/creds'),
};
