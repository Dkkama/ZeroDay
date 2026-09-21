import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import ExportDialog from "./ExportDialog.jsx";

export default function Inbox() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState(params.get("q") || "");
  const [category, setCategory] = useState(params.get("category") || "");
  const [status, setStatus] = useState(params.get("status") || "");
  const [exportOn, setExportOn] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    const query = {};
    if (q) query.q = q;
    if (category) query.category = category;
    if (status) query.status = status;
    api.emails(query).then(setRows).catch((e) => setErr(e.message));
  }, [q, category, status]);

  function open(row) {
    if (row.category === "BL_COMPARISON") nav(`/comparison?id=${row.email_id}`);
    else nav(`/inbox?open=${row.email_id}&category=${category}`);
  }

  const openId = params.get("open");
  const openRow = rows.find((r) => r.email_id === openId);

  return (
    <div>
      <div className="header">
        <h1>Inbox</h1>
        <button className="btn" onClick={() => setExportOn(true)}>Export results</button>
      </div>
      <div className="toolbar">
        <input placeholder="Search subject, id, sender" value={q}
               onChange={(e) => { setQ(e.target.value); setParams({ q: e.target.value, category, status }); }} />
        <select value={category} onChange={(e) => { setCategory(e.target.value); setParams({ q, category: e.target.value, status }); }}>
          <option value="">All categories</option>
          <option value="BL_COMPARISON">Check documents</option>
          <option value="SI_REQUEST">New SI</option>
          <option value="INVOICE_QUERY">Invoice</option>
          <option value="GENERAL">Operational</option>
          <option value="SPAM">Spam</option>
        </select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setParams({ q, category, status: e.target.value }); }}>
          <option value="">All statuses</option>
          <option value="OK">OK</option>
          <option value="MISMATCH">Mismatch</option>
          <option value="NEEDS_REVIEW">Needs review</option>
        </select>
      </div>
      {err && <div className="error">{err}</div>}
      {openRow && openRow.category !== "BL_COMPARISON" && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h3>{openRow.subject}</h3>
          <p className="muted">{openRow.from} · {openRow.caught_at}</p>
          <pre className="pre">{openRow.body}</pre>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>#</th><th>Id</th><th>Subject</th><th>Date</th><th>Category</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.email_id} className="row" onDoubleClick={() => open(r)}>
              <td>{i + 1}</td>
              <td>{r.email_id}</td>
              <td>{r.subject}</td>
              <td>{(r.caught_at || "").slice(0, 16).replace("T", " ")}</td>
              <td><span className={`chip ${r.category}`}>{r.category}</span></td>
              <td><span className={`chip ${r.status}`}>{r.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      {exportOn && <ExportDialog onClose={() => setExportOn(false)} />}
    </div>
  );
}
