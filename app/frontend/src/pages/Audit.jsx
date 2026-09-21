import { useEffect, useState } from "react";
import { api, download } from "../api";

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [limit, setLimit] = useState(200);
  const [fmt, setFmt] = useState("csv");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.audit(500).then(setRows).catch((e) => setErr(e.message));
  }, []);

  async function exp() {
    try {
      await download("audit", { fmt, limit }, `audit.${fmt === "pdf" ? "txt" : fmt}`);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <div className="header">
        <h1>Audit log</h1>
        <select className="dark-select" value={limit} onChange={(e) => setLimit(e.target.value)}>
          <option value="50">50 changes</option>
          <option value="200">200 changes</option>
          <option value="500">500 changes</option>
        </select>
        <select className="dark-select" value={fmt} onChange={(e) => setFmt(e.target.value)}>
          <option value="csv">CSV</option>
          <option value="json">JSON</option>
          <option value="xlsx">XLSX</option>
          <option value="pdf">PDF / text</option>
        </select>
        <button className="btn primary" onClick={exp}>Export the report</button>
      </div>
      {err && <div className="error">{err}</div>}
      <table>
        <thead>
          <tr><th>#</th><th>When</th><th>Actor</th><th>Document</th><th>Change</th><th>Category</th></tr>
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
    </div>
  );
}
