import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";

const ORDER = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"];
const COLORS = {
  BL_COMPARISON: "#e11d48",
  SI_REQUEST: "#3b82f6",
  INVOICE_QUERY: "#d97706",
  GENERAL: "#14b8a6",
  SPAM: "#6b7280",
  OK: "#16a34a",
  MISMATCH: "#e11d48",
  NEEDS_REVIEW: "#f59e0b",
};
const REASON_COLORS = {
  wrong_doc_type: "#e11d48",
  missing_attachment: "#3b82f6",
  unreadable: "#d97706",
  missing_value: "#a855f7",
};
const REASON_LABELS = {
  wrong_doc_type: "Wrong document type",
  missing_attachment: "Missing attachment",
  unreadable: "Unreadable file",
  missing_value: "Missing value",
};
const STATUS_LABELS = {
  OK: "Matched / no defect",
  MISMATCH: "Mismatch",
  NEEDS_REVIEW: "Needs review",
};

const tipStyle = {
  background: "#141c22",
  border: "1px solid #2a3842",
  borderRadius: 10,
  color: "#e8eef2",
};
const tipItem = { color: "#e8eef2" };
const tipLabel = { color: "#c5d0d8" };

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
  const total = catData.reduce((n, r) => n + r.value, 0) || 1;
  const statusData = Object.entries(stats.by_status).map(([k, v]) => ({
    key: k,
    name: STATUS_LABELS[k] || k,
    value: v,
  }));
  const statusTotal = statusData.reduce((n, r) => n + r.value, 0) || 1;
  const reasonData = Object.entries(stats.review_reasons || {}).map(([k, v]) => ({
    key: k,
    name: REASON_LABELS[k] || k,
    value: v,
  }));

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
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={catData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="#2a3842" vertical={false} />
              <XAxis dataKey="name" hide />
              <YAxis stroke="#8b9aa6" allowDecimals={false} />
              <Tooltip
                contentStyle={tipStyle}
                itemStyle={tipItem}
                labelStyle={tipLabel}
                formatter={(value) => [`${value} emails (${((value / total) * 100).toFixed(1)}%)`, "Count"]}
              />
              <Bar dataKey="value" name="Emails" radius={[8, 8, 0, 0]}>
                {catData.map((c) => <Cell key={c.key} fill={COLORS[c.key]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="legend-list">
            {catData.map((c) => (
              <span key={c.key}><i style={{ background: COLORS[c.key] }} />{c.name}</span>
            ))}
          </div>
        </div>
        <div className="panel">
          <h3>Compare outcomes</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={statusData}
                dataKey="value"
                nameKey="name"
                innerRadius={58}
                outerRadius={92}
                paddingAngle={2}
                label={({ name, value }) => `${((value / statusTotal) * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {statusData.map((c) => <Cell key={c.key} fill={COLORS[c.key] || "#64748b"} />)}
              </Pie>
              <Tooltip
                contentStyle={tipStyle}
                itemStyle={tipItem}
                labelStyle={tipLabel}
                formatter={(value, name) => [`${value} (${((value / statusTotal) * 100).toFixed(1)}%)`, name]}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="panel" style={{ gridColumn: "1 / -1" }}>
          <h3>Why the algorithm asked for a person</h3>
          {reasonData.length === 0 ? <p className="muted">No open review reasons in this workspace.</p> : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={reasonData}>
                  <CartesianGrid stroke="#2a3842" vertical={false} />
                  <XAxis dataKey="name" stroke="#8b9aa6" />
                  <YAxis stroke="#8b9aa6" allowDecimals={false} />
                  <Tooltip
                    contentStyle={tipStyle}
                    itemStyle={tipItem}
                    labelStyle={tipLabel}
                    formatter={(value) => [value, "Cases"]}
                  />
                  <Bar dataKey="value" name="Cases" radius={[8, 8, 0, 0]}>
                    {reasonData.map((c) => (
                      <Cell key={c.key} fill={REASON_COLORS[c.key] || "#f59e0b"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="legend-list">
                {reasonData.map((c) => (
                  <span key={c.key}><i style={{ background: REASON_COLORS[c.key] }} />{c.name}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
