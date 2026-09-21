let pending = null;

export function stageZip(file) {
  pending = file;
}

export function takeZip() {
  const file = pending;
  pending = null;
  return file;
}

export function isZip(file) {
  return Boolean(file && String(file.name || "").toLowerCase().endsWith(".zip"));
}
