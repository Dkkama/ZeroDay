import { useEffect, useState } from "react";
import { IconA11y } from "./navIcons.jsx";

const THEMES = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "hc", label: "High contrast" },
];
const SIZES = [
  { id: "sm", label: "A−" },
  { id: "md", label: "A" },
  { id: "lg", label: "A+" },
  { id: "xl", label: "A++" },
];

function apply(theme, text) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.text = text;
  localStorage.setItem("zd-theme", theme);
  localStorage.setItem("zd-text", text);
}

export default function A11yControl() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("zd-theme") || "dark");
  const [text, setText] = useState(() => localStorage.getItem("zd-text") || "md");

  useEffect(() => { apply(theme, text); }, [theme, text]);

  return (
    <div className="a11y">
      <button
        className={`a11y-btn${open ? " on" : ""}`}
        type="button"
        aria-expanded={open}
        aria-controls="a11y-panel"
        onClick={() => setOpen((v) => !v)}
      >
        <IconA11y />
        Accessibility
      </button>
      {open && (
        <div className="a11y-panel" id="a11y-panel" role="dialog" aria-label="Accessibility">
          <p>Text size</p>
          <div className="a11y-row">
            {SIZES.map((s) => (
              <button key={s.id} type="button" className={text === s.id ? "on" : ""}
                      onClick={() => setText(s.id)}>{s.label}</button>
            ))}
          </div>
          <p>Colour scheme</p>
          <div className="a11y-row">
            {THEMES.map((t) => (
              <button key={t.id} type="button" className={theme === t.id ? "on" : ""}
                      onClick={() => setTheme(t.id)}>{t.label}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
