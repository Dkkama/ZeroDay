import { useEffect, useState } from "react";
import { attachmentUrl, token } from "../api";
import { HighlightText } from "../docs.jsx";

function isTextFile(ext) {
  return ["txt", "csv", "json", "xml", "md", "log"].includes((ext || "").toLowerCase());
}

function isImage(ext) {
  return ["png", "jpg", "jpeg", "gif", "webp"].includes((ext || "").toLowerCase());
}

function isSpreadsheet(att) {
  const name = (att?.filename || "").toLowerCase();
  const ext = (att?.ext || "").toLowerCase();
  return ext === "xlsx" || ext === "xls" || name.endsWith(".xlsx") || name.endsWith(".xls");
}

function parseExtractedSheet(text) {
  if (!text) return null;
  const sheets = [];
  let current = { name: "Sheet", rows: [] };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const sheetHead = line.match(/^\[sheet:\s*(.+?)\]$/i);
    if (sheetHead) {
      if (current.rows.length) sheets.push(current);
      current = { name: sheetHead[1], rows: [] };
      continue;
    }
    current.rows.push(line.includes("|")
      ? line.split("|").map((c) => c.trim())
      : [line]);
  }
  if (current.rows.length) sheets.push(current);
  return sheets.length ? { sheets } : null;
}

function colLetter(n) {
  let s = "";
  let x = n + 1;
  while (x > 0) {
    const m = (x - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    x = Math.floor((x - 1) / 26);
  }
  return s;
}

function SheetGrid({ data }) {
  if (!data?.sheets?.length) return <p className="muted">Empty spreadsheet</p>;
  return (
    <div className="sheet">
      {data.sheets.map((s) => {
        const width = Math.max(1, ...s.rows.map((r) => r.length));
        return (
          <div key={s.name} className="sheet-block">
            <div className="sheet-name">{s.name}</div>
            <table className="excel">
              <thead>
                <tr>
                  <th className="excel-corner" />
                  {Array.from({ length: width }, (_, j) => (
                    <th key={j}>{colLetter(j)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {s.rows.map((row, i) => (
                  <tr key={i}>
                    <th className="excel-row">{i + 1}</th>
                    {Array.from({ length: width }, (_, j) => (
                      <td key={j}>{row[j] || ""}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

export default function FilePreview({ emailId, att, needles = [] }) {
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
    setSheet(isSpreadsheet(att) ? parseExtractedSheet(att?.text) : null);
    setErr("");
    setFull(false);

    async function load() {
      if (!att?.filename) return;
      if (isSpreadsheet(att)) {
        try {
          const res = await fetch(
            `${attachmentUrl(emailId, att.filename)}/sheet`,
            { headers: { Authorization: `Bearer ${token()}` }, signal: ctrl.signal },
          );
          if (res.ok) {
            const data = await res.json();
            if (!dead && data.sheets?.length) setSheet(data);
          }
        } catch (e) {
          if (e.name === "AbortError") return;
        }
        if (!dead && !parseExtractedSheet(att?.text)) {
          setErr("");
        }
        return;
      }
      const res = await fetch(attachmentUrl(emailId, att.filename), {
        headers: { Authorization: `Bearer ${token()}` },
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error("Could not open file");
      const ext = (att.ext || "").toLowerCase();
      if (isTextFile(ext)) {
        const body = await res.text();
        if (!dead) setText(body);
        return;
      }
      const type = (res.headers.get("content-type") || "").toLowerCase();
      if (ext === "pdf" && !type.includes("pdf")) {
        const body = await res.text();
        if (!dead) setText(body || att.text || "");
        return;
      }
      const blob = await res.blob();
      if (!dead) setUrl(URL.createObjectURL(blob));
    }

    load().catch((e) => {
      if (e.name === "AbortError") return;
      if (!dead && !isSpreadsheet(att)) {
        setErr(att?.notes || e.message || "Could not open file");
      }
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [emailId, att?.filename, att?.text]);

  if (!att) return <div className="preview"><p className="muted">No file</p></div>;
  const ext = (att.ext || "").toLowerCase();
  const spreadsheet = isSpreadsheet(att);

  const body = (
    <>
      {spreadsheet && <SheetGrid data={sheet || parseExtractedSheet(att.text)} />}
      {!spreadsheet && ext === "pdf" && url && <iframe title={att.filename} src={url} />}
      {!spreadsheet && isImage(ext) && url && <img className="preview-img" alt={att.filename} src={url} />}
      {!spreadsheet && (text || att.text) && (isTextFile(ext) || text) && (
        <HighlightText text={text || att.text} needles={needles} />
      )}
      {!spreadsheet && !isTextFile(ext) && ext !== "pdf" && !isImage(ext) && (
        <pre className="pre">{text || att.text || att.filename}</pre>
      )}
      {err && <p className="muted">{err}</p>}
      {!spreadsheet && !url && !text && !err && <p className="muted">Loading {att.filename}…</p>}
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
