import { useEffect, useState } from "react";
import { api, download } from "../api";
import ExportDialog from "./ExportDialog.jsx";

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [imap, setImap] = useState({});
  const [jobs, setJobs] = useState([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [exportOn, setExportOn] = useState(false);

  async function refresh() {
    const [s, j] = await Promise.all([api.settings(), api.jobs()]);
    setSettings(s);
    setImap(s.imap || {});
    setJobs(j);
  }

  useEffect(() => { refresh().catch((e) => setErr(e.message)); }, []);

  async function saveProvider(llm_provider) {
    await api.saveSettings({ llm_provider });
    await refresh();
  }

  return (
    <div>
      <div className="header"><h1>Settings</h1></div>
      {err && <div className="error">{err}</div>}
      {msg && <p>{msg}</p>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>Model</h3>
        <p className="muted">Cursor is for testing (large limit). Vertex Gemini is the production demo — a few live calls only. The seeded inbox does not spend Gemini quota.</p>
        <button className={`btn ${settings?.llm_provider === "cursor" ? "primary" : ""}`}
                onClick={() => saveProvider("cursor")}>Test — Cursor</button>
        {" "}
        <button className={`btn ${settings?.llm_provider === "vertex" ? "primary" : ""}`}
                onClick={() => saveProvider("vertex")}>Production demo — Vertex</button>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>Inbox source</h3>
        <p className="muted">Load the 520-email sample (Flash 1.00 labels, no live model), upload a hackathon zip, or fetch a mail server over IMAP.</p>
        <button className="btn primary" onClick={async () => {
          setMsg("Loading sample…");
          const out = await api.seed();
          setMsg(`Loaded ${out.loaded} emails from the sample inbox.`);
        }}>Load sample dataset</button>
        {" "}
        <label className="btn">
          Upload zip
          <input type="file" hidden accept=".zip" onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            const out = await api.upload(file);
            setMsg(`Upload job #${out.job.id} queued (${out.count} emails).`);
            refresh();
          }} />
        </label>
        <div className="fields" style={{ marginTop: 16 }}>
          {["host", "port", "username", "password", "folder"].map((k) => (
            <div className="field-box" key={k}>
              <b>{k}</b>
              <input type={k === "password" ? "password" : "text"}
                     value={imap[k] ?? ""}
                     onChange={(e) => setImap({ ...imap, [k]: e.target.value })} />
            </div>
          ))}
        </div>
        <label className="muted">
          <input type="checkbox" checked={imap.tls !== false}
                 onChange={(e) => setImap({ ...imap, tls: e.target.checked })} /> TLS
        </label>
        <div style={{ height: 10 }} />
        <button className="btn" onClick={async () => {
          await api.saveSettings({ imap });
          await api.imapTest();
          setMsg("IMAP connected.");
        }}>Connect</button>
        {" "}
        <button className="btn" onClick={async () => {
          await api.saveSettings({ imap });
          const out = await api.imapFetch(10);
          setMsg(`IMAP job #${out.job.id} fetching ${out.count} messages.`);
          refresh();
        }}>Fetch now</button>
        <p className="muted">Last sync: {settings?.imap?.last_sync || "never"} · {settings?.imap?.status}</p>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>Jobs</h3>
        {jobs.length === 0 && <p className="muted">No ingest or process jobs yet.</p>}
        <table>
          <thead><tr><th>Id</th><th>Kind</th><th>Provider</th><th>Status</th><th>Progress</th><th></th></tr></thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id}>
                <td>{j.id}</td><td>{j.kind}</td><td>{j.provider}</td>
                <td>{j.status}</td>
                <td>{j.done}/{j.total} failed {j.failed}</td>
                <td>{j.status === "failed" && (
                  <button className="btn" onClick={() => api.retry(j.id).then(refresh)}>Retry</button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>Exports</h3>
        <button className="btn" onClick={() => setExportOn(true)}>Export results (choose filters)</button>
        {" "}
        <button className="btn" onClick={() => download("submission", {}, "submission.json")}>
          Export scorer submission.json
        </button>
      </div>
      {exportOn && <ExportDialog onClose={() => setExportOn(false)} />}
    </div>
  );
}
