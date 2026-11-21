const STORAGE_KEY = "kb_web_auth";

export function loadAuth() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  } catch {
    return null;
  }
}

export function saveAuth(session) {
  if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  else localStorage.removeItem(STORAGE_KEY);
}

function errorMessage(data, status) {
  return data?.error?.message || data?.detail || `Ошибка ${status}`;
}

export async function api(path, options = {}, session = loadAuth()) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  if (options.structuredUi) headers["X-KB-Structured-UI"] = "1";

  let response = await fetch(path, { ...options, headers });
  if (response.status === 401 && session?.refresh_token && !options._retried) {
    const refreshed = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    });
    if (refreshed.ok) {
      const next = await refreshed.json();
      const saved = { ...session, ...next, mode: session.mode };
      saveAuth(saved);
      return api(path, { ...options, _retried: true }, saved);
    }
    saveAuth(null);
  }
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!response.ok) {
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

export async function apiBlob(path, session = loadAuth()) {
  const headers = {};
  if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  let response = await fetch(path, { headers });
  if (response.status === 401 && session?.refresh_token) {
    const refreshed = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    });
    if (refreshed.ok) {
      const next = await refreshed.json();
      saveAuth({ ...session, ...next, mode: session.mode });
      return apiBlob(path, { ...session, ...next });
    }
  }
  if (!response.ok) throw new Error(`Ошибка ${response.status}`);
  return response.blob();
}
