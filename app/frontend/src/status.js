export function statusLabel(row) {
  if (row?.fixed || (row?.human_validated && row?.status === "MISMATCH")) {
    return "OK (Fixed)";
  }
  return row?.status || "OK";
}

export function statusClass(row) {
  if (row?.fixed || (row?.human_validated && row?.status === "MISMATCH")) {
    return "OK";
  }
  return row?.status || "OK";
}
