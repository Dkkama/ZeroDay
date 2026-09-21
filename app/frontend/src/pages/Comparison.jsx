import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import FilePreview from "./FilePreview.jsx";
import { statusClass, statusLabel } from "../status";
import { SortTh, emailNum, nextSort, sortRows } from "../sort.jsx";
import { ExtractText, FIELD_LABELS, mismatchNeedles, valuesDiffer } from "../docs.jsx";

export default function Comparison() {
  const [params, setParams] = useSearchParams();
  const [queue, setQueue] = useState([]);
  const [doc, setDoc] = useState(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [err, setErr] = useState("");
  const [sort, setSort] = useState({ key: "num", dir: "desc" });
  const writes = useRef(Promise.resolve());
  const pending = useRef({});
  const saveTimer = useRef(null);
  const id = params.get("id");

  function later(task) {
    writes.current = writes.current.then(task).catch((e) => setErr(e.message));
  }

  function flushNow(emailId) {
    clearTimeout(saveTimer.current);
    const edits = Object.entries(pending.current).map(([name, value]) => ({ name, source: "custom", value }));
    pending.current = {};
    if (edits.length) later(() => api.editFields(emailId, edits));
  }

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
    setDraft({});
    api.email(id).then(setDoc).catch((e) => setErr(e.message));
  }, [id]);

  function open(row) {
    if (id && id !== row.email_id) flushNow(id);
    setParams({ id: row.email_id });
    setEditing(false);
    setDraft({});
  }

  function idx() {
    return queue.findIndex((r) => r.email_id === id);
  }

  function go(delta) {
    const i = idx() + delta;
    if (i >= 0 && i < queue.length) open(queue[i]);
  }

  function pick(field, source, value) {
    const current = (doc?.field_view || []).find((f) => f.name === field);
    let resolved = value ?? "";
    if (source === "si") resolved = current?.si || "";
    if (source === "bl") resolved = current?.bl || "";
    setDraft((prev) => ({ ...prev, [field]: resolved }));
    const emailId = id;
    if (source === "custom") {
      pending.current[field] = resolved;
      clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => flushNow(emailId), 300);
      return;
    }
    flushNow(emailId);
    later(() => api.editFields(emailId, [{ name: field, source: "custom", value: resolved }]));
  }

  function finishEdit() {
    if (!editing) {
      setEditing(true);
      return;
    }
    flushNow(id);
    setEditing(false);
  }

  function validate() {
    const leaving = id;
    flushNow(leaving);
    setQueue((rows) => rows.map((r) => (
      r.email_id === leaving ? { ...r, fixed: true, human_validated: true } : r
    )));
    const next = queue.find((r) => r.email_id !== leaving && !r.fixed && !r.human_validated);
    if (next) open(next);
    else { setParams({}); setDoc(null); }
    later(() => api.validate(leaving));
  }

  if (!id) {
    return (
      <div>
        <div className="header"><h1>Review requests</h1></div>
        <p className="muted">Click a row to review it.</p>
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
                <tr key={r.email_id} className="row" onClick={() => open(r)}>
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

  if (!doc || doc.email_id !== id) {
    const hint = queue.find((r) => r.email_id === id);
    return (
      <div>
        <div className="header">
          <h1>Review requests</h1>
          <div className="header-actions">
            <button className="btn" onClick={() => { setParams({}); setDoc(null); }}>Back to list</button>
          </div>
        </div>
        <p className="muted">{id}{hint?.subject ? ` · ${hint.subject}` : ""}</p>
        <p className="muted">Opening…</p>
      </div>
    );
  }
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
          <button className="btn" onClick={finishEdit}>{editing ? "Done" : "Edit"}</button>
          <button className="btn primary" onClick={validate}>Validate</button>
        </div>
      </div>
      <p className="muted">{doc.email_id} · {doc.subject} · {statusLabel(doc)} · {doc.review_reason || (doc.defect_fields || []).join(", ")}</p>

      <div className="fields" key={doc.email_id}>
        {(doc.field_view || []).map((raw) => {
          const chosen = Object.prototype.hasOwnProperty.call(draft, raw.name) ? draft[raw.name] : null;
          const f = chosen === null ? raw : {
            ...raw,
            value: chosen,
            source: chosen === raw.si ? "si" : chosen === raw.bl ? "bl" : "custom",
          };
          const differs = valuesDiffer(f.si, f.bl);
          const decided = String(chosen ?? (doc.resolved_fields || {})[raw.name] ?? "").trim().length > 0;
          const tone = differs ? (decided ? " decided" : " mismatch") : "";
          return (
          <div className={`field-box${tone}`} key={`${doc.email_id}-${f.name}`}>
            <b>{FIELD_LABELS[f.name] || f.name}</b>
            {f.empty ? (
              <input
                placeholder="AI could not read this field — double-click to type"
                value={f.value || ""}
                onChange={(e) => pick(f.name, "custom", e.target.value)}
                onDoubleClick={(e) => e.currentTarget.removeAttribute("readonly")}
                readOnly={!editing}
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
                  value={f.value || ""}
                  readOnly={!editing}
                  onChange={(e) => pick(f.name, "custom", e.target.value)}
                  onDoubleClick={(e) => { e.currentTarget.readOnly = false; }}
                />
              </>
            )}
          </div>
          );
        })}
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
