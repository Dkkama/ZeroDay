import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";

const ORDER = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"];
const COLORS = {
  BL_COMPARISON: "#e11d48",
  SI_REQUEST: "#3b82f6",
  INVOICE_QUERY: "#d97706",
  GENERAL: "#0f766e",
  SPAM: "#6b7280",
  OK: "#16a34a",
  MISMATCH: "#e11d48",
  NEEDS_REVIEW: "#f59e0b",
};

export default function Dashboard() {
  const nav = useNavigate();
  const [stats, setStats] = useState(null);
  const [meta, setMeta] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([api.stats(), api.meta()])
      .then(([s, m]) => { setStats(s); setMeta(m); })
      .catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="error">{err}</div>;
  if (!stats) return <p className="muted">Loading desk… first seed can take a minute.</p>;

  const catData = ORDER.map((k) => ({
    key: k,
    name: meta?.categories?.[k]?.label || k,
    value: stats.by_category[k] || 0,
  }));
  const statusData = Object.entries(stats.by_status).map(([k, v]) => ({ name: k, value: v }));
  const reasonData = Object.entries(stats.review_reasons || {}).map(([k, v]) => ({ name: k, value: v }));

  return (
    <div>
      <div className="header"><h1>Dashboard</h1></div>
      <div className="cards">
        {catData.map((c) => (
          <div key={c.key} className="card" onClick={() => nav(`/inbox?category=${c.key}`)}>
            <div className="label">{c.name}</div>
            <div className="num" style={{ color: COLORS[c.key] }}>{c.value}</div>
          </div>
        ))}
      </div>
      <div className="banner">
        There are <b>{stats.check_documents}</b> requests to check documents.
        {" "}<b>{stats.needs_human}</b> still need a human (mismatch or unreadable / missing / wrong file).
        {meta?.demo_score != null && (
          <span className="muted"> Seeded Flash run scored {Number(meta.demo_score).toFixed(4)} on the 520-email key.</span>
        )}
      </div>
      <div className="charts">
        <div className="panel">
          <h3>Category mix</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={catData}>
              <XAxis dataKey="key" hide />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value">
                {catData.map((c) => <Cell key={c.key} fill={COLORS[c.key]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Compare outcomes</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80}>
                {statusData.map((c) => <Cell key={c.name} fill={COLORS[c.name] || "#64748b"} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="panel" style={{ gridColumn: "1 / -1" }}>
          <h3>Why the algorithm asked for a person</h3>
          {reasonData.length === 0 ? <p className="muted">No open review reasons in this workspace.</p> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={reasonData}>
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
