import { useEffect, useRef } from "react";

const KINDS = [
  { ext: ".pdf", color: "#e11d48" },
  { ext: ".xlsx", color: "#22c55e" },
  { ext: ".csv", color: "#84cc16" },
  { ext: ".json", color: "#f59e0b" },
  { ext: ".txt", color: "#94a3b8" },
];

const COUNT = 28;
const LINK = 150;
const REACH = 260;

function hexRgb(hex) {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
}

function makeNodes(w, h) {
  return Array.from({ length: COUNT }, (_, i) => {
    const kind = KINDS[i % KINDS.length];
    return {
      x: 40 + Math.random() * Math.max(1, w - 80),
      y: 40 + Math.random() * Math.max(1, h - 80),
      vx: (Math.random() - 0.5) * 0.28,
      vy: (Math.random() - 0.5) * 0.28,
      kind,
    };
  });
}

function drawFile(ctx, node, alpha, glow) {
  const { x, y, kind } = node;
  const [r, g, b] = hexRgb(kind.color);
  const w = 56;
  const h = 58;
  const fold = 11;
  ctx.save();
  ctx.translate(x, y);
  ctx.globalAlpha = alpha;
  if (glow > 0.05) {
    ctx.shadowColor = `rgba(${r},${g},${b},${0.35 + glow * 0.55})`;
    ctx.shadowBlur = 8 + glow * 22;
  }
  ctx.beginPath();
  ctx.moveTo(-w / 2, -h / 2);
  ctx.lineTo(w / 2 - fold, -h / 2);
  ctx.lineTo(w / 2, -h / 2 + fold);
  ctx.lineTo(w / 2, h / 2);
  ctx.lineTo(-w / 2, h / 2);
  ctx.closePath();
  ctx.fillStyle = `rgba(${r},${g},${b},0.16)`;
  ctx.fill();
  ctx.strokeStyle = `rgba(${r},${g},${b},0.85)`;
  ctx.lineWidth = 1.4;
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(w / 2 - fold, -h / 2);
  ctx.lineTo(w / 2 - fold, -h / 2 + fold);
  ctx.lineTo(w / 2, -h / 2 + fold);
  ctx.closePath();
  ctx.fillStyle = `rgba(${r},${g},${b},0.45)`;
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = `rgba(${r},${g},${b},0.95)`;
  ctx.font = "600 13px 'Segoe UI', system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(kind.ext, 0, 4);
  ctx.restore();
}

export default function FileConstellation() {
  const ref = useRef(null);
  const mouse = useRef({ x: -9999, y: -9999 });

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let nodes = [];
    let frame = 0;
    let running = true;

    let view = { w: 0, h: 0 };
    function size() {
      const parent = canvas.parentElement;
      const w = parent?.clientWidth || window.innerWidth;
      const h = parent?.clientHeight || window.innerHeight;
      if (w === view.w && h === view.h) return view;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      view = { w, h };
      if (!nodes.length) nodes = makeNodes(w, h);
      return view;
    }

    function near(n) {
      const dx = n.x - mouse.current.x;
      const dy = n.y - mouse.current.y;
      return Math.max(0, 1 - Math.hypot(dx, dy) / REACH);
    }

    function tick() {
      if (!running) return;
      const { w, h } = size();
      ctx.clearRect(0, 0, w, h);
      if (!reduce) {
        for (const n of nodes) {
          n.x += n.vx;
          n.y += n.vy;
          if (n.x < 30 || n.x > w - 30) n.vx *= -1;
          if (n.y < 30 || n.y > h - 30) n.vy *= -1;
          n.x = Math.min(w - 24, Math.max(24, n.x));
          n.y = Math.min(h - 24, Math.max(24, n.y));
        }
      }
      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d > LINK) continue;
          const heat = (near(a) + near(b)) / 2;
          const [r, g, bl] = hexRgb(a.kind.color);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = `rgba(${r},${g},${bl},${0.06 + (1 - d / LINK) * 0.16 + heat * 0.28})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
      for (const n of nodes) {
        const prox = near(n);
        drawFile(ctx, n, 0.38 + prox * 0.58, prox);
      }
      frame = requestAnimationFrame(tick);
    }

    function onMove(e) {
      const box = canvas.getBoundingClientRect();
      mouse.current = { x: e.clientX - box.left, y: e.clientY - box.top };
    }
    function onLeave() {
      mouse.current = { x: -9999, y: -9999 };
    }

    const host = canvas.parentElement;
    host.addEventListener("mousemove", onMove);
    host.addEventListener("mouseleave", onLeave);
    window.addEventListener("resize", size);
    size();
    frame = requestAnimationFrame(tick);
    return () => {
      running = false;
      cancelAnimationFrame(frame);
      host.removeEventListener("mousemove", onMove);
      host.removeEventListener("mouseleave", onLeave);
      window.removeEventListener("resize", size);
    };
  }, []);

  return <canvas className="login-sky" ref={ref} aria-hidden="true" />;
}
