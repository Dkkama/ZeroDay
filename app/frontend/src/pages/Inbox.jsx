import { Fragment, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import ExportDialog from "./ExportDialog.jsx";
import { statusClass, statusLabel } from "../status";
import Select from "../Select.jsx";
import { HighlightText, mismatchNeedles } from "../docs.jsx";
import { SortTh, emailNum, nextSort, sortRows } from "../sort.jsx";

function InboxPreview({ id, onReview }) {
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setDoc(null);
    setErr("");
    api.email(id).then(setDoc).catch((e) => setErr(e.message));
  }, [id]);

  if (err) return <div className="error">{err}</div>;
  if (!doc) return <p className="muted">Opening…</p>;
  const needles = mismatchNeedles(doc.si_fields, doc.bl_fields);
  const si = (doc.attachments || []).find((a) => a.kind === "si");
  const bl = (doc.attachments || []).find((a) => a.kind === "bl");

  return (
    <div className="inline-preview">
      <p className="muted">{doc.from} · {(doc.caught_at || "").slice(0, 16).replace("T", " ")}</p>
      {doc.body ? <HighlightText text={doc.body} /> : null}
      {(si?.text || bl?.text) && (
        <div className="split">
          <div>
            <h3>SI — {si?.filename || "none"}</h3>
            <HighlightText text={si?.text || ""} needles={needles} />
          </div>
          <div>
            <h3>BL — {bl?.filename || "none"}</h3>
            <HighlightText text={bl?.text || ""} needles={needles} />
          </div>
        </div>
      )}
      {doc.category === "BL_COMPARISON" && (
        <button className="btn" type="button" onClick={onReview}>Open in review</button>
      )}
    </div>
  );
}

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

  function toggle(row) {
    const next = { q, category, status };
    if (params.get("open") !== row.email_id) next.open = row.email_id;
    setParams(next);
  }

  const openId = params.get("open");
  const colCount = 7;
  const shown = sortRows(rows, sort, (r, key) => {
    if (key === "num") return emailNum(r);
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
              <Fragment key={r.email_id}>
                <tr className={`row${openId === r.email_id ? " row-open" : ""}`} onClick={() => toggle(r)}>
                  <td className="col-num">{emailNum(r)}</td>
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
                {openId === r.email_id && (
                  <tr className="preview-row">
                    <td colSpan={colCount}>
                      <InboxPreview id={r.email_id} onReview={() => nav(`/comparison?id=${r.email_id}`)} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {exportOn && <ExportDialog onClose={() => setExportOn(false)} />}
    </div>
  );
}
