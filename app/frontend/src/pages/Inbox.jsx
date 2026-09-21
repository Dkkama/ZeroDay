import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import ExportDialog from "./ExportDialog.jsx";
import { statusClass, statusLabel } from "../status";
import Select from "../Select.jsx";
import { SortTh, emailNum, nextSort, rowOpen, sortRows } from "../sort.jsx";

export default function Inbox() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState(params.get("q") || "");
  const [category, setCategory] = useState(params.get("category") || "");
  const [status, setStatus] = useState(params.get("status") || "");
  const [exportOn, setExportOn] = useState(false);
  const [err, setErr] = useState("");
  const [sort, setSort] = useState({ key: "num", dir: "desc" });

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
  const shown = sortRows(rows, sort, (r, key) => {
    if (key === "num") return emailNum(r.email_id);
    if (key === "id") return r.email_id || "";
    if (key === "subject") return r.subject || "";
    if (key === "date") return r.caught_at || "";
    if (key === "category") return r.category || "";
    if (key === "status") return statusLabel(r);
    return "";
  });

  return (
    <div>
      <div className="header">
        <h1>Inbox</h1>
        <div className="header-actions">
          <button className="btn" onClick={() => setExportOn(true)}>Export results</button>
        </div>
      </div>
      <div className="toolbar mail-toolbar">
        <input placeholder="Search subject, id, sender" value={q}
               onChange={(e) => { setQ(e.target.value); setParams({ q: e.target.value, category, status }); }} />
        <Select value={category} onChange={(e) => { setCategory(e.target.value); setParams({ q, category: e.target.value, status }); }}>
          <option value="">All categories</option>
          <option value="BL_COMPARISON">Check documents</option>
          <option value="SI_REQUEST">New SI</option>
          <option value="INVOICE_QUERY">Invoice</option>
          <option value="GENERAL">Operational</option>
          <option value="SPAM">Spam</option>
        </Select>
        <Select value={status} onChange={(e) => { setStatus(e.target.value); setParams({ q, category, status: e.target.value }); }}>
          <option value="">All statuses</option>
          <option value="OK">OK</option>
          <option value="MISMATCH">Mismatch</option>
          <option value="NEEDS_REVIEW">Needs review</option>
        </Select>
      </div>
      {err && <div className="error">{err}</div>}
      {openRow && openRow.category !== "BL_COMPARISON" && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h3>{openRow.subject}</h3>
          <p className="muted">{openRow.from} · {openRow.caught_at}</p>
          <pre className="pre">{openRow.body}</pre>
        </div>
      )}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <SortTh className="col-num" label="#" col="num" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="hide-sm" label="Id" col="id" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-subject" label="Subject" col="subject" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="hide-sm" label="Date" col="date" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-chip hide-sm" label="Category" col="category" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-chip hide-sm" label="Status" col="status" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-meta show-sm" label="Type" col="status" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.email_id} className="row" {...rowOpen(() => open(r))}>
                <td className="col-num">{emailNum(r.email_id)}</td>
                <td className="hide-sm">{r.email_id}</td>
                <td className="col-subject">{r.subject}</td>
                <td className="hide-sm">{(r.caught_at || "").slice(0, 16).replace("T", " ")}</td>
                <td className="col-chip hide-sm"><span className={`chip ${r.category}`}>{r.category}</span></td>
                <td className="col-chip hide-sm"><span className={`chip ${statusClass(r)}`}>{statusLabel(r)}</span></td>
                <td className="col-meta show-sm">
                  <span className={`chip ${r.category}`}>{r.category}</span>
                  <span className={`chip ${statusClass(r)}`}>{statusLabel(r)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {exportOn && <ExportDialog onClose={() => setExportOn(false)} />}
    </div>
  );
}
