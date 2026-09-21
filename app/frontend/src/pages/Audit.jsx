import { useEffect, useState } from "react";
import { api, download } from "../api";
import { auditRowsToPdf } from "../pdf.js";
import Select from "../Select.jsx";
import { SortTh, nextSort, sortRows } from "../sort.jsx";

function AuditWhen({ value }) {
  const raw = (value || "").slice(0, 16).replace("T", " ");
  const [day, time] = raw.split(" ");
  return (
    <>
      <span className="date-part">{day}</span>
      {time ? <>{" "}<span className="date-part">{time}</span></> : null}
    </>
  );
}

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [exportOn, setExportOn] = useState(false);
  const [limit, setLimit] = useState(200);
  const [fmt, setFmt] = useState("csv");
  const [err, setErr] = useState("");
  const [sort, setSort] = useState({ key: "num", dir: "desc" });

  useEffect(() => {
    api.audit(500).then(setRows).catch((e) => setErr(e.message));
  }, []);

  async function exp() {
    try {
      if (fmt === "pdf") {
        const data = await api.audit(limit);
        const bytes = auditRowsToPdf(data);
        const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = "audit.pdf";
        a.click();
        URL.revokeObjectURL(url);
      } else {
        await download("audit", { fmt, limit }, `audit.${fmt}`);
      }
      setExportOn(false);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <div className="header">
        <h1>Audit log</h1>
        <div className="header-actions">
          <button className="btn primary" onClick={() => setExportOn(true)}>Export the report</button>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <SortTh className="col-num hide-sm" label="#" col="num" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-date" label="Date" col="date" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-chip" label="Actor" col="actor" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-num" label="Document" col="document" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-subject" label="Change" col="change" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
              <SortTh className="col-chip" label="Category" col="category" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
            </tr>
          </thead>
          <tbody>
            {sortRows(rows, sort, (r, key) => {
              if (key === "num") return Number(r.id) || 0;
              if (key === "date") return r.created_at || "";
              if (key === "actor") return r.actor || "";
              if (key === "document") return r.email_id || "";
              if (key === "change") return r.change_type || "";
              if (key === "category") return r.category || "";
              return "";
            }).map((r) => (
              <tr key={r.id}>
                <td className="col-num hide-sm">{r.id}</td>
                <td className="col-date"><AuditWhen value={r.created_at} /></td>
                <td className="col-chip"><span className={`chip ${r.actor}`}>{r.actor}</span></td>
                <td className="col-num">{r.email_id}</td>
                <td className="col-subject">{r.change_type}</td>
                <td className="col-chip"><span className={`chip ${r.category}`}>{r.category}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {exportOn && (
        <div className="modal-back" onClick={() => setExportOn(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Export the report</h3>
            <p className="muted">Choose how many log rows to include and the file type.</p>
            <label className="muted">How many logs</label>
            <Select className="dark-select" value={limit} onChange={(e) => setLimit(e.target.value)}>
              <option value="50">Last 50</option>
              <option value="200">Last 200</option>
              <option value="500">Last 500</option>
            </Select>
            <div style={{ height: 12 }} />
            <label className="muted">Format</label>
            <Select className="dark-select" value={fmt} onChange={(e) => setFmt(e.target.value)}>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
              <option value="xlsx">XLSX</option>
              <option value="pdf">PDF</option>
              <option value="txt">TXT</option>
            </Select>
            <div style={{ height: 16 }} />
            <button className="btn primary" onClick={exp}>Download</button>
            {" "}
            <button className="btn" onClick={() => setExportOn(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
