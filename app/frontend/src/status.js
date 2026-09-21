function humanFixed(row) {
  if (row?.fixed) return true;
  return Boolean(row?.human_validated) && (row?.status === "MISMATCH" || row?.status === "NEEDS_REVIEW");
}

export function statusLabel(row) {
  if (humanFixed(row)) return "Fixed by human";
  return row?.status || "OK";
}

export function statusClass(row) {
  if (humanFixed(row)) return "OK";
  return row?.status || "OK";
}
