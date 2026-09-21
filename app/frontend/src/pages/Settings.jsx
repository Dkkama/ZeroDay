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

  useEffect(() => {
    const busy = jobs.some((j) => j.status === "queued" || j.status === "running");
    if (!busy) return undefined;
    const t = setInterval(() => refresh().catch((e) => setErr(e.message)), 2000);
    return () => clearInterval(t);
  }, [jobs]);

  async function run(label, fn) {
    setErr("");
    setMsg(label);
    try {
      const out = await fn();
      await refresh();
      return out;
    } catch (e) {
      setErr(e.message || String(e));
      setMsg("");
      await refresh().catch(() => {});
      return null;
    }
  }

  async function saveProvider(llm_provider) {
    await run(`Using ${llm_provider}.`, () => api.saveSettings({ llm_provider }));
  }

  return (
    <div>
      <div className="header"><h1>Settings</h1></div>
      {err && <div className="error">{err}</div>}
      {msg && <p>{msg}</p>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>Model</h3>
        <p className="muted">Cursor is for testing (large limit). Vertex Gemini is the production demo — a few live calls only. The seeded inbox does not spend Gemini quota.</p>
        <div className="btn-row">
          <button className={`btn ${settings?.llm_provider === "cursor" ? "primary" : ""}`}
                  onClick={() => saveProvider("cursor")}>Test — Cursor</button>
          <button className={`btn ${settings?.llm_provider === "vertex" ? "primary" : ""}`}
                  onClick={() => saveProvider("vertex")}>Production demo — Vertex</button>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>Inbox source</h3>
        <p className="muted">Load the 520-email sample (Flash 1.00 labels, no live model), upload a hackathon zip, or fetch a mail server over IMAP.</p>
        <div className="btn-row">
        <button className="btn primary" onClick={async () => {
          const out = await run("Loading sample…", () => api.seed());
          if (out) setMsg(`Loaded ${out.loaded} emails from the sample inbox.`);
        }}>Load sample dataset</button>
        {" "}
        <button className="btn" onClick={async () => {
          const out = await run("Loading one email with attachments…", () => api.ingestOne());
          if (out) {
            setMsg(`Loaded ${out.email_id} (${(out.attachments || []).join(", ") || "no files"}). Open Inbox to preview.`);
          }
        }}>Load one email with attachments</button>
        {" "}
        <button className="btn" onClick={async () => {
          const out = await run("Queueing Vertex on one email…", async () => {
            await api.saveSettings({ llm_provider: "vertex" });
            return api.processOne();
          });
          if (out) setMsg(`Job #${out.job.id} processing ${out.email_id} with ${out.provider}.`);
        }}>Process one email — Vertex</button>
        {" "}
        <label className="btn">
          Upload zip
          <input type="file" hidden accept=".zip" onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            const out = await run("Uploading zip…", () => api.upload(file));
            if (out) setMsg(`Upload job #${out.job.id} queued (${out.count} emails).`);
          }} />
        </label>
        </div>
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
        <div className="btn-row" style={{ marginTop: 10 }}>
          <button className="btn" onClick={async () => {
            const out = await run("Connecting IMAP (fails in ~8s if the host is wrong)…", async () => {
              await api.saveSettings({ imap });
              return api.imapTest();
            });
            if (out) setMsg("IMAP connected.");
          }}>Connect</button>
          <button className="btn" onClick={async () => {
            const out = await run("Fetching IMAP…", async () => {
              await api.saveSettings({ imap });
              return api.imapFetch(10);
            });
            if (out) setMsg(`IMAP job #${out.job.id} fetching ${out.count} messages.`);
          }}>Fetch now</button>
        </div>
        <p className="muted">Last sync: {settings?.imap?.last_sync || "never"} · {settings?.imap?.status}</p>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>Jobs</h3>
        {jobs.length === 0 && <p className="muted">No ingest or process jobs yet.</p>}
        <div className="table-scroll">
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
      </div>

      <div className="panel">
        <h3>Exports</h3>
        <div className="btn-row">
          <button className="btn" onClick={() => setExportOn(true)}>Export results (choose filters)</button>
          <button className="btn" onClick={() => download("submission", {}, "submission.json")}>
            Export scorer submission.json
          </button>
        </div>
      </div>
      {exportOn && <ExportDialog onClose={() => setExportOn(false)} />}
    </div>
  );
}
