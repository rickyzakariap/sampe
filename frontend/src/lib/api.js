import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const TOKEN_KEY = "sampe_session_token";
export const ADMIN_TOKEN_KEY = "sampe_admin_token";

export const currentMonth = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export const shiftMonth = (m, delta) => {
  const d = new Date(Number(m.slice(0, 4)), Number(m.slice(5, 7)) - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export const errMsg = (e, fallback = "Terjadi kesalahan. Coba lagi.") => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg).filter(Boolean).join(" ") || fallback;
  return fallback;
};

const withToken = (key, onUnauthorized) => {
  const inst = axios.create({ baseURL: API, withCredentials: true });
  inst.interceptors.request.use((cfg) => {
    const t = localStorage.getItem(key);
    if (t) cfg.headers.Authorization = `Bearer ${t}`;
    return cfg;
  });
  inst.interceptors.response.use((r) => r, (e) => {
    if (e?.response?.status === 401 && localStorage.getItem(key)) {
      localStorage.removeItem(key);
      onUnauthorized?.();
    }
    return Promise.reject(e);
  });
  return inst;
};

const http = withToken(TOKEN_KEY, () => window.dispatchEvent(new Event("pulse:logout")));
const adminHttp = withToken(ADMIN_TOKEN_KEY, () => window.dispatchEvent(new Event("pulse:admin-logout")));
const d = (p) => p.then((r) => r.data);

export const api = {
  googleSession: (session_id) => d(axios.post(`${API}/auth/google-session`, { session_id }, { withCredentials: true })),
  claim: (code) => d(http.post("/auth/claim", { code })),
  logout: () => d(http.post("/auth/logout")),
  activation: (email, ref_id) => d(axios.post(`${API}/activation/lookup`, { email, ref_id })),
  me: () => d(http.get("/auth/me")),
  getConfig: () => d(http.get("/config")),
  saveConfig: (payload) => d(http.post("/config", payload)),
  configHistory: () => d(http.get("/config/history")),
  updateCompany: (company_name) => d(http.patch("/config/company", { company_name })),
  getEntries: (module, month) => d(http.get("/entries", { params: { module, month } })),
  createEntry: (payload) => d(http.post("/entries", payload)),
  deleteEntry: (id) => d(http.delete(`/entries/${id}`)),
  dashboard: (month) => d(http.get("/dashboard", { params: { month } })),
  months: () => d(http.get("/months")),
  analyze: (month) => d(http.post("/ai/analyze", { month })),
  seed: (company_name) => d(http.post("/seed", { company_name })),
  reset: () => d(http.post("/reset")),
  compare: (month) => d(http.get("/compare", { params: { month } })),
};

export const adminApi = {
  login: (email, password) => d(axios.post(`${API}/auth/admin-login`, { email, password })),
  me: () => d(adminHttp.get("/auth/admin-me")),
  list: () => d(adminHttp.get("/admin/licenses")),
  create: (label, duration_days, email) => d(adminHttp.post("/admin/licenses", { label, duration_days, email: email || null })),
  lynk: () => d(adminHttp.get("/admin/lynk")),
  saveLynk: (body) => d(adminHttp.put("/admin/lynk", body)),
  orders: () => d(adminHttp.get("/admin/orders")),
  webhookLogs: () => d(adminHttp.get("/admin/webhook-logs")),
  reprocess: (received_at) => d(adminHttp.post("/admin/webhook-logs/process", null, { params: { received_at } })),
  extend: (id, days) => d(adminHttp.post(`/admin/licenses/${id}/extend`, { days })),
  revoke: (id) => d(adminHttp.post(`/admin/licenses/${id}/revoke`)),
  restore: (id) => d(adminHttp.post(`/admin/licenses/${id}/restore`)),
};
