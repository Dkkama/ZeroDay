export const FIELD_LABELS = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify party",
  port_of_loading: "Port of loading",
  port_of_discharge: "Port of discharge",
  container_count: "Container count",
  gross_weight_kg: "Gross weight (kg)",
};

export function valuesDiffer(a, b) {
  return String(a ?? "").trim().toLowerCase() !== String(b ?? "").trim().toLowerCase();
}

export function mismatchNeedles(si, bl) {
  const out = [];
  for (const key of Object.keys(FIELD_LABELS)) {
    const left = String(si?.[key] ?? "").trim();
    const right = String(bl?.[key] ?? "").trim();
    if (!valuesDiffer(left, right)) continue;
    if (left.length >= 4) out.push(left);
    if (right.length >= 4) out.push(right);
  }
  return out;
}

export function HighlightText({ text, needles = [] }) {
  if (!text) return <p className="muted">No text</p>;
  const lines = String(text).split(/\n/);
  return (
    <pre className="pre">
      {lines.map((line, i) => {
        const low = line.toLowerCase();
        const hit = needles.some((n) => low.includes(n.toLowerCase()));
        return (
          <div key={i} className={hit ? "line-bad" : undefined}>{line || " "}</div>
        );
      })}
    </pre>
  );
}

export function ExtractText({ fields, other }) {
  return (
    <div className="extract">
      {Object.entries(FIELD_LABELS).map(([key, label]) => {
        const value = String(fields?.[key] ?? "").trim();
        const bad = valuesDiffer(value, other?.[key]);
        return (
          <div key={key} className={bad ? "extract-line line-bad" : "extract-line"}>
            <b>{label}</b>
            <span>{value || "—"}</span>
          </div>
        );
      })}
    </div>
  );
}
