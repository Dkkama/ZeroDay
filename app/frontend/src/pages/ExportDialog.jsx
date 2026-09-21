import { useState } from "react";
import { download } from "../api";

const STATUS = [
  { id: "OK", label: "Succeeded / no mismatch" },
  { id: "MISMATCH", label: "Mismatched" },
  { id: "NEEDS_REVIEW", label: "Needs human review" },
];
const CATS = [
  { id: "BL_COMPARISON", label: "Check documents" },
  { id: "SI_REQUEST", label: "New shipping instructions" },
  { id: "INVOICE_QUERY", label: "Invoice questions" },
  { id: "GENERAL", label: "Operational updates" },
  { id: "SPAM", label: "Spam" },
];

export default function ExportDialog({ onClose }) {
  const [statuses, setStatuses] = useState(["OK", "MISMATCH", "NEEDS_REVIEW"]);
  const [categories, setCategories] = useState(CATS.map((c) => c.id));
  const [fmt, setFmt] = useState("csv");
  const [validated, setValidated] = useState("");
  const [err, setErr] = useState("");

  function toggle(list, setList, id) {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  async function go(preset) {
    setErr("");
    try {
      const query = { fmt };
      if (preset) query.preset = preset;
      else {
        query.statuses = statuses.join(",");
        query.categories = categories.join(",");
        if (validated === "yes") query.human_validated = "true";
        if (validated === "no") query.human_validated = "false";
      }
      await download("results", query, `results.${fmt}`);
      onClose();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Export results</h3>
        <p className="muted">Choose what to include. Audit history is a different export on the Audit page.</p>
        <div className="toolbar">
          <button className="btn" onClick={() => go("all")}>All</button>
          <button className="btn" onClick={() => go("succeeded")}>Succeeded only</button>
          <button className="btn" onClick={() => go("mismatched")}>Mismatches only</button>
          <button className="btn" onClick={() => go("succeeded_and_mismatched")}>Succeeded + mismatched</button>
          <button className="btn" onClick={() => go("review")}>Review queue</button>
        </div>
        <div className="checks">
          {STATUS.map((s) => (
            <label key={s.id}>
              <input type="checkbox" checked={statuses.includes(s.id)}
                     onChange={() => toggle(statuses, setStatuses, s.id)} />
              {s.label}
            </label>
          ))}
          {CATS.map((s) => (
            <label key={s.id}>
              <input type="checkbox" checked={categories.includes(s.id)}
                     onChange={() => toggle(categories, setCategories, s.id)} />
              {s.label}
            </label>
          ))}
        </div>
        <label className="muted">Human-validated</label>
        <select className="dark-select" value={validated} onChange={(e) => setValidated(e.target.value)}>
          <option value="">Any</option>
          <option value="yes">Only validated</option>
          <option value="no">Not yet validated</option>
        </select>
        <div style={{ height: 10 }} />
        <select className="dark-select" value={fmt} onChange={(e) => setFmt(e.target.value)}>
          <option value="csv">CSV</option>
          <option value="json">JSON</option>
          <option value="xlsx">XLSX</option>
        </select>
        <div style={{ height: 14 }} />
        <button className="btn primary" onClick={() => go(null)}>Export selection</button>
        {" "}
        <button className="btn" onClick={onClose}>Cancel</button>
        {err && <div className="error">{err}</div>}
      </div>
    </div>
  );
}
