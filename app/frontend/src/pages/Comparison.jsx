import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import FilePreview from "./FilePreview.jsx";
import { statusClass, statusLabel } from "../status";
import { SortTh, emailNum, nextSort, rowOpen, sortRows } from "../sort.jsx";
import { ExtractText, FIELD_LABELS, mismatchNeedles, valuesDiffer } from "../docs.jsx";

export default function Comparison() {
  const [params, setParams] = useSearchParams();
  const [queue, setQueue] = useState([]);
  const [doc, setDoc] = useState(null);
  const [editing, setEditing] = useState(false);
  const [err, setErr] = useState("");
  const [sort, setSort] = useState({ key: "num", dir: "desc" });
  const id = params.get("id");

  async function loadList() {
    const rows = await api.emails({ queue: "true" });
    setQueue(rows);
    return rows;
  }

  useEffect(() => {
    loadList().catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!id) { setDoc(null); return; }
    setDoc(null);
    api.email(id).then(setDoc).catch((e) => setErr(e.message));
  }, [id]);

  function open(row) {
    setParams({ id: row.email_id });
    setEditing(false);
  }

  function idx() {
    return queue.findIndex((r) => r.email_id === id);
  }

  function go(delta) {
    const i = idx() + delta;
    if (i >= 0 && i < queue.length) open(queue[i]);
  }

  async function validate() {
    await api.validate(id);
    const rows = await loadList();
    const next = rows.find((r) => r.email_id !== id);
    if (next) open(next);
    else { setParams({}); setDoc(null); }
  }

  async function pick(field, source, value) {
    await api.editFields(id, [{ name: field, source, value }]);
    setDoc(await api.email(id));
  }

  if (!id) {
    return (
      <div>
        <div className="header"><h1>Review requests</h1></div>
        <p className="muted">Open a row to review. On a phone, tap; on a desktop, double-click.</p>
        {err && <div className="error">{err}</div>}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <SortTh className="col-num" label="#" col="num" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
                <SortTh className="col-subject" label="File / subject" col="subject" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
                <SortTh className="hide-sm" label="Date caught" col="date" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
                <SortTh label="Reason" col="reason" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              </tr>
            </thead>
            <tbody>
              {sortRows(queue, sort, (r, key) => {
                if (key === "num") return emailNum(r);
                if (key === "subject") return r.subject || r.email_id || "";
                if (key === "date") return r.caught_at || "";
                if (key === "reason") return `${statusLabel(r)} ${r.review_reason || (r.defect_fields || []).join(", ")}`;
                return "";
              }).map((r) => (
                <tr key={r.email_id} className="row" {...rowOpen(() => open(r))}>
                  <td className="col-num">{emailNum(r)}</td>
                  <td className="col-subject">{r.subject || r.email_id}</td>
                  <td className="hide-sm">{(r.caught_at || "").slice(0, 16).replace("T", " ")}</td>
                  <td>
                    <span className={`chip ${statusClass(r)}`}>{statusLabel(r)}</span>
                    {r.review_reason || (r.defect_fields || []).length ? (
                      <span className="chip-extra"> {r.review_reason || (r.defect_fields || []).join(", ")}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (!doc || doc.email_id !== id) return <p className="muted">Opening {id}…</p>;
  const si = (doc.attachments || []).find((a) => a.kind === "si");
  const bl = (doc.attachments || []).find((a) => a.kind === "bl");
  const needles = mismatchNeedles(doc.si_fields, doc.bl_fields);

  return (
    <div>
      <div className="header">
        <h1>Review requests</h1>
        <div className="header-actions">
          <button className="btn" onClick={() => { setParams({}); setDoc(null); }}>Back to list</button>
          <button className="btn" onClick={() => go(-1)} disabled={idx() <= 0}>Previous</button>
          <button className="btn" onClick={() => go(1)} disabled={idx() >= queue.length - 1}>Next</button>
          <button className="btn" onClick={() => setEditing((v) => !v)}>{editing ? "Done" : "Edit"}</button>
          <button className="btn primary" onClick={validate}>Validate</button>
        </div>
      </div>
      <p className="muted">{doc.email_id} · {doc.subject} · {statusLabel(doc)} · {doc.review_reason || (doc.defect_fields || []).join(", ")}</p>

      <div className="fields" key={doc.email_id}>
        {(doc.field_view || []).map((f) => (
          <div className={`field-box${valuesDiffer(f.si, f.bl) ? " mismatch" : ""}`} key={`${doc.email_id}-${f.name}`}>
            <b>{FIELD_LABELS[f.name] || f.name}</b>
            {f.empty ? (
              <input
                placeholder="AI could not read this field — double-click to type"
                defaultValue={f.value}
                onDoubleClick={(e) => e.currentTarget.removeAttribute("readonly")}
                readOnly={!editing}
                onBlur={(e) => pick(f.name, "custom", e.target.value)}
              />
            ) : (
              <>
                <div className="choices">
                  {f.si && (
                    <button className={f.source === "si" || f.source === "both" ? "on" : ""}
                            onClick={() => pick(f.name, "si")}>SI: {f.si}</button>
                  )}
                  {f.bl && f.bl !== f.si && (
                    <button className={f.source === "bl" ? "on" : ""}
                            onClick={() => pick(f.name, "bl")}>BL: {f.bl}</button>
                  )}
                </div>
                <input
                  defaultValue={f.value}
                  readOnly={!editing}
                  onDoubleClick={(e) => { e.currentTarget.readOnly = false; }}
                  onBlur={(e) => pick(f.name, "custom", e.target.value)}
                />
              </>
            )}
          </div>
        ))}
      </div>

      <div className="split">
        <div>
          <h3>Shipping instruction</h3>
          <ExtractText fields={doc.si_fields} other={doc.bl_fields} />
        </div>
        <div>
          <h3>Bill of lading</h3>
          <ExtractText fields={doc.bl_fields} other={doc.si_fields} />
        </div>
      </div>
      <div className="split">
        <div>
          <h3>SI original — {si?.filename || "none"}</h3>
          <FilePreview key={`${doc.email_id}-si`} emailId={doc.email_id} att={si || (doc.attachments || [])[0]} needles={needles} />
        </div>
        <div>
          <h3>BL original — {bl?.filename || "none"}</h3>
          <FilePreview key={`${doc.email_id}-bl`} emailId={doc.email_id} att={bl || (doc.attachments || [])[1]} needles={needles} />
        </div>
      </div>
    </div>
  );
}
