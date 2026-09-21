import { useEffect, useState } from "react";
import { attachmentUrl, token } from "../api";

export default function FilePreview({ emailId, att }) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [sheet, setSheet] = useState(null);
  const [full, setFull] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let dead = false;
    const ctrl = new AbortController();
    setUrl("");
    setText("");
    setSheet(null);
    setErr("");
    setFull(false);

    async function load() {
      if (!att?.filename) return;
      const ext = (att.ext || "").toLowerCase();
      if (ext === "xlsx" || ext === "xls") {
        const res = await fetch(
          `${attachmentUrl(emailId, att.filename)}/sheet`,
          { headers: { Authorization: `Bearer ${token()}` }, signal: ctrl.signal },
        );
        if (!res.ok) throw new Error("Could not read spreadsheet");
        const data = await res.json();
        if (!dead) setSheet(data);
        return;
      }
      const res = await fetch(attachmentUrl(emailId, att.filename), {
        headers: { Authorization: `Bearer ${token()}` },
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error("Could not open file");
      if (ext === "txt" || ext === "csv") {
        const body = await res.text();
        if (!dead) setText(body);
        return;
      }
      const blob = await res.blob();
      if (!dead) setUrl(URL.createObjectURL(blob));
    }

    load().catch((e) => {
      if (e.name === "AbortError") return;
      if (!dead) setErr(att?.text || att?.notes || e.message || "Could not open file");
    });
    return () => {
      dead = true;
      ctrl.abort();
      setUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return "";
      });
    };
  }, [emailId, att?.filename]);

  if (!att) return <div className="preview"><p className="muted">No file</p></div>;
  const ext = (att.ext || "").toLowerCase();

  const body = (
    <>
      {sheet && (
        <div className="sheet">
          {sheet.sheets.map((s) => (
            <div key={s.name}>
              <div className="sheet-name">{s.name}</div>
              <table>
                <tbody>
                  {s.rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        i === 0 ? <th key={j}>{cell}</th> : <td key={j}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
      {ext === "pdf" && url && <iframe title={att.filename} src={url} />}
      {(ext === "txt" || ext === "csv" || (text && !sheet && ext !== "pdf")) && (
        <pre className="pre">{text || att.text}</pre>
      )}
      {url && ext !== "pdf" && !sheet && (
        <pre className="pre">{att.text || `${att.filename} (${ext})`}</pre>
      )}
      {err && <p className="muted">{err}</p>}
      {!sheet && !url && !text && !err && <p className="muted">Loading {att.filename}…</p>}
    </>
  );

  return (
    <div className="preview-wrap">
      <div className="preview-bar">
        <span>{att.filename}</span>
        <button type="button" className="btn" onClick={() => setFull(true)}>Full screen</button>
      </div>
      <div className="preview">{body}</div>
      {full && (
        <div className="modal-back preview-full" onClick={() => setFull(false)}>
          <div className="preview-full-card" onClick={(e) => e.stopPropagation()}>
            <div className="preview-bar">
              <span>{att.filename}</span>
              <button type="button" className="btn" onClick={() => setFull(false)}>Close</button>
            </div>
            <div className="preview preview-full-body">{body}</div>
          </div>
        </div>
      )}
    </div>
  );
}
