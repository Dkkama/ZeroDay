import { useEffect, useRef } from "react";

const KINDS = [
  { ext: ".pdf", color: "#fb7185", shape: "file" },
  { ext: ".xlsx", color: "#22c55e", shape: "file" },
  { ext: ".csv", color: "#84cc16", shape: "file" },
  { ext: ".json", color: "#fbbf24", shape: "file" },
  { ext: ".txt", color: "#94a3b8", shape: "file" },
  { ext: "folder", color: "#e8b86d", shape: "folder" },
  { ext: "mail", color: "#7dd3fc", shape: "mail" },
];

const COUNT = 56;
const LINK = 110;
const REACH = 220;
const TOUCH = 20;
const COMFORT = 78;
const CRUISE = 0.11;
const MAX_SPEED = 0.42;

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
    const ang = Math.random() * Math.PI * 2;
    return {
      x: 30 + Math.random() * Math.max(1, w - 60),
      y: 30 + Math.random() * Math.max(1, h - 60),
      vx: Math.cos(ang) * CRUISE,
      vy: Math.sin(ang) * CRUISE,
      kind,
    };
  });
}

function drawFile(ctx, w, h, r, g, b) {
  const fold = 6;
  ctx.beginPath();
  ctx.moveTo(-w / 2, -h / 2);
  ctx.lineTo(w / 2 - fold, -h / 2);
  ctx.lineTo(w / 2, -h / 2 + fold);
  ctx.lineTo(w / 2, h / 2);
  ctx.lineTo(-w / 2, h / 2);
  ctx.closePath();
  ctx.fillStyle = `rgba(${r},${g},${b},0.16)`;
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(w / 2 - fold, -h / 2);
  ctx.lineTo(w / 2 - fold, -h / 2 + fold);
  ctx.lineTo(w / 2, -h / 2 + fold);
  ctx.closePath();
  ctx.fillStyle = `rgba(${r},${g},${b},0.45)`;
  ctx.fill();
}

function drawFolder(ctx, w, h, r, g, b) {
  ctx.beginPath();
  ctx.moveTo(-w / 2, -h / 2 + 5);
  ctx.lineTo(-w / 2 + 7, -h / 2);
  ctx.lineTo(-1, -h / 2);
  ctx.lineTo(2, -h / 2 + 5);
  ctx.lineTo(w / 2, -h / 2 + 5);
  ctx.lineTo(w / 2, h / 2);
  ctx.lineTo(-w / 2, h / 2);
  ctx.closePath();
  ctx.fillStyle = `rgba(${r},${g},${b},0.2)`;
  ctx.fill();
  ctx.stroke();
}

function drawMail(ctx, w, h, r, g, b) {
  ctx.beginPath();
  ctx.roundRect(-w / 2, -h / 2 + 2, w, h - 4, 3);
  ctx.fillStyle = `rgba(${r},${g},${b},0.16)`;
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(-w / 2, -h / 2 + 2);
  ctx.lineTo(0, 2);
  ctx.lineTo(w / 2, -h / 2 + 2);
  ctx.stroke();
}

function drawNode(ctx, node, alpha, glow) {
  const { x, y, kind } = node;
  const [r, g, b] = hexRgb(kind.color);
  const w = 28;
  const h = 30;
  ctx.save();
  ctx.translate(x, y);
  ctx.globalAlpha = alpha;
  if (glow > 0.05) {
    ctx.shadowColor = `rgba(${r},${g},${b},${0.35 + glow * 0.55})`;
    ctx.shadowBlur = 6 + glow * 16;
  }
  ctx.strokeStyle = `rgba(${r},${g},${b},0.88)`;
  ctx.lineWidth = 1.1;
  if (kind.shape === "folder") drawFolder(ctx, w, h, r, g, b);
  else if (kind.shape === "mail") drawMail(ctx, w, h, r, g, b);
  else drawFile(ctx, w, h, r, g, b);
  ctx.shadowBlur = 0;
  ctx.fillStyle = `rgba(${r},${g},${b},0.95)`;
  ctx.font = "600 8px 'Segoe UI', system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(kind.ext, 0, kind.shape === "file" ? 3 : 5);
  ctx.restore();
}

function steer(n, mx, my) {
  const dx = n.x - mx;
  const dy = n.y - my;
  const dist = Math.hypot(dx, dy) || 0.001;
  const ux = dx / dist;
  const uy = dy / dist;
  if (dist < TOUCH) {
    n.vx += ux * 0.012;
    n.vy += uy * 0.012;
  } else if (dist < COMFORT) {
    n.vx += ux * 0.0035;
    n.vy += uy * 0.0035;
  } else if (dist < REACH) {
    n.vx -= ux * 0.0016;
    n.vy -= uy * 0.0016;
  }
}

function limitSpeed(n) {
  const sp = Math.hypot(n.vx, n.vy);
  if (sp > MAX_SPEED) {
    n.vx = (n.vx / sp) * MAX_SPEED;
    n.vy = (n.vy / sp) * MAX_SPEED;
  } else if (sp > CRUISE) {
    n.vx *= 0.985;
    n.vy *= 0.985;
  } else if (sp < CRUISE * 0.55) {
    const f = (CRUISE * 0.7) / (sp || 0.001);
    n.vx *= f;
    n.vy *= f;
  }
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
      return Math.max(0, 1 - Math.hypot(n.x - mouse.current.x, n.y - mouse.current.y) / REACH);
    }

    function tick() {
      if (!running) return;
      const { w, h } = size();
      ctx.clearRect(0, 0, w, h);
      if (!reduce) {
        const mx = mouse.current.x;
        const my = mouse.current.y;
        for (const n of nodes) {
          if (mx > -1000) steer(n, mx, my);
          limitSpeed(n);
          n.x += n.vx;
          n.y += n.vy;
          if (n.x < 18 || n.x > w - 18) n.vx *= -1;
          if (n.y < 18 || n.y > h - 18) n.vy *= -1;
          n.x = Math.min(w - 16, Math.max(16, n.x));
          n.y = Math.min(h - 16, Math.max(16, n.y));
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
          ctx.strokeStyle = `rgba(${r},${g},${bl},${0.05 + (1 - d / LINK) * 0.14 + heat * 0.26})`;
          ctx.lineWidth = 0.9;
          ctx.stroke();
        }
      }
      for (const n of nodes) {
        const prox = near(n);
        drawNode(ctx, n, 0.36 + prox * 0.6, prox);
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
