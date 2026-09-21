const TOKEN_KEY = "zeroday_token";

export function token() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(value) {
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

async function req(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  if (opts.body && !(opts.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    setToken("");
    if (!path.includes("/login")) window.location.href = "/login";
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      detail = await res.text();
    }
    throw new Error(detail);
  }
  const type = res.headers.get("content-type") || "";
  if (type.includes("application/json")) return res.json();
  return res;
}

export const api = {
  login: (email, password) =>
    req("/api/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => req("/api/me"),
  meta: () => req("/api/meta"),
  stats: () => req("/api/stats"),
  emails: (params = {}) => req("/api/emails?" + new URLSearchParams(params)),
  email: (id) => req(`/api/emails/${id}`),
  validate: (id) => req(`/api/emails/${id}/validate`, { method: "POST" }),
  editFields: (id, fields) =>
    req(`/api/emails/${id}/fields`, { method: "POST", body: JSON.stringify(fields) }),
  audit: (limit = 400) => req(`/api/audit?limit=${limit}`),
  settings: () => req("/api/settings"),
  saveSettings: (body) => req("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
  jobs: () => req("/api/jobs"),
  seed: () => req("/api/ingest/sample", { method: "POST" }),
  upload: (file) => {
    const data = new FormData();
    data.append("file", file);
    return req("/api/ingest/upload", { method: "POST", body: data });
  },
  imapTest: () => req("/api/ingest/imap/test", { method: "POST" }),
  imapFetch: (limit = 10) =>
    req("/api/ingest/imap/fetch", { method: "POST", body: JSON.stringify({ limit }) }),
  ingestOne: () => req("/api/ingest/one", { method: "POST" }),
  processOne: () => req("/api/process/one", { method: "POST" }),
  process: (email_ids) =>
    req("/api/process", { method: "POST", body: JSON.stringify({ email_ids }) }),
  retry: (id) => req(`/api/jobs/${id}/retry`, { method: "POST" }),
};

export function exportUrl(kind, query) {
  const q = new URLSearchParams(query);
  return `/api/export/${kind}?${q}`;
}

export async function download(kind, query, filename) {
  const res = await fetch(exportUrl(kind, query), {
    headers: { Authorization: `Bearer ${token()}` },
  });
  if (!res.ok) throw new Error("export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function attachmentUrl(emailId, filename) {
  return `/api/emails/${emailId}/attachments/${encodeURIComponent(filename)}`;
}
