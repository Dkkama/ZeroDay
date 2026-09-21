import { useEffect, useState } from "react";
import { attachmentUrl, token } from "../api";

export default function FilePreview({ emailId, att }) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");

  useEffect(() => {
    let dead = false;
    async function load() {
      if (!att) return;
      const res = await fetch(attachmentUrl(emailId, att.filename), {
        headers: { Authorization: `Bearer ${token()}` },
      });
      const ext = (att.ext || "").toLowerCase();
      if (ext === "txt" || ext === "csv") {
        const body = await res.text();
        if (!dead) setText(body);
        return;
      }
      const blob = await res.blob();
      if (!dead) setUrl(URL.createObjectURL(blob));
    }
    load().catch(() => setText(att?.text || att?.notes || "Could not open file"));
    return () => { dead = true; if (url) URL.revokeObjectURL(url); };
  }, [emailId, att?.filename]);

  if (!att) return <div className="preview"><p className="muted">No file</p></div>;
  const ext = (att.ext || "").toLowerCase();
  if (att.status && att.status !== "ok" && !att.text && !url) {
    return <div className="preview"><p className="muted">{att.status}: {att.notes || "unreadable"}</p></div>;
  }
  if (ext === "pdf" && url) {
    return <div className="preview"><iframe title={att.filename} src={url} /></div>;
  }
  if ((ext === "txt" || ext === "csv" || text) && !url) {
    return <pre className="pre">{text || att.text}</pre>;
  }
  if (url) {
    return (
      <div className="preview">
        <p className="muted">{att.filename} ({ext || "file"}) — download if the browser cannot preview Word/Excel.</p>
        <a className="btn" href={url} download={att.filename}>Download</a>
        {att.text && <pre className="pre">{att.text}</pre>}
      </div>
    );
  }
  return <div className="preview"><p className="muted">Loading {att.filename}…</p></div>;
}
