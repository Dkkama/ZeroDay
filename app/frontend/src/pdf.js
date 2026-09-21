function escapePdf(text) {
  return String(text || "")
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)")
    .replace(/[^\x09\x20-\x7e]/g, "?");
}

function encode(str) {
  const out = new Uint8Array(str.length);
  for (let i = 0; i < str.length; i += 1) out[i] = str.charCodeAt(i) & 0xff;
  return out;
}

function concat(parts) {
  const size = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(size);
  let at = 0;
  for (const p of parts) {
    out.set(p, at);
    at += p.length;
  }
  return out;
}

export function linesToPdf(lines) {
  const perPage = 48;
  const rows = lines.length ? lines : [""];
  const chunks = [];
  for (let i = 0; i < rows.length; i += perPage) chunks.push(rows.slice(i, i + perPage));

  const objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""];
  const contentIds = [];
  const pageIds = [];
  const streams = [];

  for (const chunk of chunks) {
    const cmds = ["BT", "/F1 10 Tf", "40 760 Td", "13 TL"];
    chunk.forEach((line, i) => {
      cmds.push(`(${escapePdf(line.slice(0, 110))}) Tj`);
      if (i !== chunk.length - 1) cmds.push("T*");
    });
    cmds.push("ET");
    streams.push(encode(cmds.join("\n")));
    objects.push(null);
    contentIds.push(objects.length);
    objects.push(null);
    pageIds.push(objects.length);
  }
  objects.push("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>");
  const fontId = objects.length;
  objects[1] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pageIds.length} >>`;
  pageIds.forEach((pid, i) => {
    objects[pid - 1] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents ${contentIds[i]} 0 R /Resources << /Font << /F1 ${fontId} 0 R >> >> >>`;
  });

  const parts = [encode("%PDF-1.4\n")];
  const offsets = [0];
  objects.forEach((obj, idx) => {
    const num = idx + 1;
    offsets.push(parts.reduce((n, p) => n + p.length, 0));
    if (contentIds.includes(num)) {
      const body = streams[contentIds.indexOf(num)];
      parts.push(encode(`${num} 0 obj\n<< /Length ${body.length} >>\nstream\n`));
      parts.push(body);
      parts.push(encode("\nendstream\nendobj\n"));
    } else {
      parts.push(encode(`${num} 0 obj\n${obj}\nendobj\n`));
    }
  });

  const xrefAt = parts.reduce((n, p) => n + p.length, 0);
  let xref = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (let i = 1; i < offsets.length; i += 1) {
    xref += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  xref += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`;
  parts.push(encode(xref));
  return concat(parts);
}

export function auditRowsToPdf(rows) {
  const lines = ["ZeroDay audit log"];
  for (const row of rows) {
    lines.push(
      `#${row.id}  ${String(row.created_at || "").slice(0, 19)}  ${row.actor}  ${row.email_id}  ${row.change_type}`
    );
  }
  return linesToPdf(lines);
}
