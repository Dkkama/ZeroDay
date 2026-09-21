export function emailNum(rowOrId) {
  if (rowOrId && typeof rowOrId === "object") {
    if (rowOrId.seq != null && rowOrId.seq !== "") return Number(rowOrId.seq);
    rowOrId = rowOrId.email_id;
  }
  const m = String(rowOrId || "").match(/^email_(\d+)$/);
  return m ? Number(m[1]) : 0;
}

export function nextSort(sort, key) {
  if (sort.key === key) return { key, dir: sort.dir === "asc" ? "desc" : "asc" };
  return { key, dir: "asc" };
}

export function sortRows(rows, sort, valueOf) {
  const mul = sort.dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = valueOf(a, sort.key);
    const bv = valueOf(b, sort.key);
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * mul;
    return String(av ?? "").localeCompare(String(bv ?? ""), undefined, {
      numeric: true,
      sensitivity: "base",
    }) * mul;
  });
}

export function rowOpen(open) {
  return {
    onClick: () => {
      if (window.matchMedia("(max-width: 820px)").matches) open();
    },
    onDoubleClick: () => open(),
  };
}

export function SortTh({ label, col, sort, onSort, className = "" }) {
  const on = sort.key === col;
  return (
    <th className={`sort-th${on ? " sort-on" : ""}${className ? ` ${className}` : ""}`} onClick={() => onSort(col)}>
      {label}
      {on ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}
    </th>
  );
}
