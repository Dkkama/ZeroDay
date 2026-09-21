import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, setToken, token } from "./api";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Inbox from "./pages/Inbox.jsx";
import Comparison from "./pages/Comparison.jsx";
import Audit from "./pages/Audit.jsx";
import Settings from "./pages/Settings.jsx";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/inbox", label: "Inbox" },
  { to: "/comparison", label: "Comparison requests" },
  { to: "/audit", label: "Audit log" },
];

function Sidebar() {
  const loc = useLocation();
  const nav = useNavigate();
  return (
    <aside className="sidebar">
      <div className="brand">
        <b>ZERODAY</b>
        <span>Shipping document desk</span>
      </div>
      <nav className="nav">
        {NAV.map((item) => (
          <a key={item.to} href={item.to} className={loc.pathname === item.to ? "active" : ""}
             onClick={(e) => { e.preventDefault(); nav(item.to); }}>
            {item.label}
          </a>
        ))}
      </nav>
      <div className="nav-foot nav">
        <a href="/settings" className={loc.pathname === "/settings" ? "active" : ""}
           onClick={(e) => { e.preventDefault(); nav("/settings"); }}>
          Settings
        </a>
        <button className="navlink" onClick={() => { setToken(""); nav("/login"); }}>
          Sign out
        </button>
      </div>
    </aside>
  );
}

function Guard({ children }) {
  const [ok, setOk] = useState(Boolean(token()));
  useEffect(() => {
    if (!token()) return;
    api.me().then(() => setOk(true)).catch(() => setOk(false));
  }, []);
  if (!token() || !ok) return <Navigate to="/login" replace />;
  return (
    <div className="shell">
      <Sidebar />
      <main className="page">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Guard><Dashboard /></Guard>} />
      <Route path="/inbox" element={<Guard><Inbox /></Guard>} />
      <Route path="/comparison" element={<Guard><Comparison /></Guard>} />
      <Route path="/audit" element={<Guard><Audit /></Guard>} />
      <Route path="/settings" element={<Guard><Settings /></Guard>} />
    </Routes>
  );
}
