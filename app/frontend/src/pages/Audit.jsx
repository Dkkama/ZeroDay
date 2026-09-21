import { useEffect, useState } from "react";
import { api, download } from "../api";
import { auditRowsToPdf } from "../pdf.js";
import { SortTh, nextSort, sortRows } from "../sort.jsx";

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
        <button className="btn primary" onClick={() => setExportOn(true)}>Export the report</button>
      </div>
      {err && <div className="error">{err}</div>}
      <table>
        <thead>
          <tr>
            <SortTh label="#" col="num" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
            <SortTh label="Date" col="date" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
            <SortTh label="Actor" col="actor" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
            <SortTh label="Document" col="document" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
            <SortTh label="Change" col="change" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
            <SortTh label="Category" col="category" sort={sort} onSort={(col) => setSort((s) => nextSort(s, col))} />
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
              <td>{r.id}</td>
              <td>{(r.created_at || "").slice(0, 19).replace("T", " ")}</td>
              <td><span className={`chip ${r.actor}`}>{r.actor}</span></td>
              <td>{r.email_id}</td>
              <td>{r.change_type}</td>
              <td><span className={`chip ${r.category}`}>{r.category}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      {exportOn && (
        <div className="modal-back" onClick={() => setExportOn(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Export the report</h3>
            <p className="muted">Choose how many log rows to include and the file type.</p>
            <label className="muted">How many logs</label>
            <select className="dark-select" value={limit} onChange={(e) => setLimit(e.target.value)}>
              <option value="50">Last 50</option>
              <option value="200">Last 200</option>
              <option value="500">Last 500</option>
            </select>
            <div style={{ height: 12 }} />
            <label className="muted">Format</label>
            <select className="dark-select" value={fmt} onChange={(e) => setFmt(e.target.value)}>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
              <option value="xlsx">XLSX</option>
              <option value="pdf">PDF</option>
              <option value="txt">TXT</option>
            </select>
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
