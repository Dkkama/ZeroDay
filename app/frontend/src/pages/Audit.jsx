import { useEffect, useState } from "react";
import { api, download } from "../api";

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [exportOn, setExportOn] = useState(false);
  const [limit, setLimit] = useState(200);
  const [fmt, setFmt] = useState("csv");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.audit(500).then(setRows).catch((e) => setErr(e.message));
  }, []);

  async function exp() {
    try {
      await download("audit", { fmt, limit }, `audit.${fmt}`);
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
          <tr><th>#</th><th>Date</th><th>Actor</th><th>Document</th><th>Change</th><th>Category</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
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
