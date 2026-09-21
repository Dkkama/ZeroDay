import { useEffect, useRef, useState } from "react";

function hasFiles(e) {
  return [...(e.dataTransfer?.types || [])].includes("Files");
}

export function ZipZone({ onFile }) {
  const [over, setOver] = useState(false);

  function take(file) {
    if (file) onFile(file);
  }

  return (
    <label
      className={`zip-zone${over ? " over" : ""}`}
      onDragEnter={(e) => { if (hasFiles(e)) { e.preventDefault(); setOver(true); } }}
      onDragOver={(e) => { if (hasFiles(e)) { e.preventDefault(); setOver(true); } }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files?.[0]);
      }}
    >
      <input type="file" hidden accept=".zip,application/zip" onChange={(e) => {
        take(e.target.files?.[0]);
        e.target.value = "";
      }} />
      <b>Drop an inbox zip</b>
      <span>or click to choose a file. Classification starts as soon as it lands, using the model selected above.</span>
    </label>
  );
}

export function PageDrop({ onZip }) {
  const [on, setOn] = useState(false);
  const depth = useRef(0);

  useEffect(() => {
    function enter(e) {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth.current += 1;
      setOn(true);
    }
    function leave() {
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setOn(false);
    }
    function over(e) {
      if (hasFiles(e)) e.preventDefault();
    }
    function drop(e) {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth.current = 0;
      setOn(false);
      const file = e.dataTransfer.files?.[0];
      if (file) onZip(file);
    }
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [onZip]);

  if (!on) return null;
  return (
    <div className="zip-overlay">
      <div className="zip-overlay-card">
        <b>Drop the inbox zip</b>
        <p>Settings will open and classification will start with the model you have selected.</p>
      </div>
    </div>
  );
}
