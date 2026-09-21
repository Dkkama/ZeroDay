import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, setToken, token } from "./api";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Inbox from "./pages/Inbox.jsx";
import Comparison from "./pages/Comparison.jsx";
import Audit from "./pages/Audit.jsx";
import Settings from "./pages/Settings.jsx";
import A11yControl from "./A11yControl.jsx";
import { PageDrop } from "./ZipDrop.jsx";
import { stageZip } from "./zipDrop.js";
import {
  IconAudit, IconBurger, IconCompare, IconDashboard, IconInbox, IconSettings, IconSignOut,
} from "./navIcons.jsx";

const NAV = [
  { to: "/", label: "Dashboard", Icon: IconDashboard },
  { to: "/inbox", label: "Inbox", Icon: IconInbox },
  { to: "/comparison", label: "Review requests", Icon: IconCompare },
  { to: "/audit", label: "Audit log", Icon: IconAudit },
];

function isMobileNav() {
  return window.matchMedia("(max-width: 820px)").matches;
}

function Sidebar({ open, onToggle, onGo, mobile }) {
  const loc = useLocation();
  return (
    <aside className={`sidebar${open ? "" : " is-collapsed"}`} aria-expanded={open}
           aria-hidden={mobile && !open}
           {...(mobile && !open ? { inert: true } : {})}>
      <div className="brand">
        <button className="sidebar-burger" type="button" onClick={onToggle}
                aria-label={open ? "Collapse sidebar" : "Expand sidebar"} title={open ? "Collapse" : "Expand"}>
          <IconBurger />
        </button>
        <div className="brand-full">
          <b>ZERODAY</b>
          <span>Shipping document desk</span>
        </div>
      </div>
      <nav className="nav">
        {NAV.map((item) => (
          <a key={item.to} href={item.to} className={loc.pathname === item.to ? "active" : ""}
             title={item.label} aria-label={item.label}
             onClick={(e) => { e.preventDefault(); onGo(item.to); }}>
            <item.Icon />
            <span className="nav-label">{item.label}</span>
          </a>
        ))}
      </nav>
      <div className="nav-foot nav">
        <a href="/settings" className={loc.pathname === "/settings" ? "active" : ""}
           title="Settings" aria-label="Settings"
           onClick={(e) => { e.preventDefault(); onGo("/settings"); }}>
          <IconSettings />
          <span className="nav-label">Settings</span>
        </a>
        <button className="navlink" title="Sign out" aria-label="Sign out" onClick={() => onGo("/login", true)}>
          <IconSignOut />
          <span className="nav-label">Sign out</span>
        </button>
      </div>
    </aside>
  );
}

function Guard() {
  const nav = useNavigate();
  const loc = useLocation();
  const [ok, setOk] = useState(Boolean(token()));
  const [mobile, setMobile] = useState(() => isMobileNav());
  const [navOpen, setNavOpen] = useState(() => !isMobileNav() && localStorage.getItem("zd-sidebar") !== "0");
  useEffect(() => {
    if (!token()) return;
    api.me().then(() => setOk(true)).catch(() => setOk(false));
  }, []);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 820px)");
    const onChange = () => {
      setMobile(mq.matches);
      if (mq.matches) setNavOpen(false);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  function setNav(next) {
    setNavOpen(next);
    if (!isMobileNav()) localStorage.setItem("zd-sidebar", next ? "1" : "0");
  }
  function toggleNav() {
    setNav(!navOpen);
  }
  function go(to, signOut) {
    if (signOut) setToken("");
    nav(to);
    if (isMobileNav()) setNav(false);
  }
  if (!token() || !ok) return <Navigate to="/login" replace />;
  return (
    <div className={`shell${navOpen ? "" : " nav-hidden"}`}>
      {navOpen && <button className="nav-scrim" type="button" aria-label="Close menu" onClick={toggleNav} />}
      <Sidebar open={navOpen} onToggle={toggleNav} onGo={go} mobile={mobile} />
      <div className="main-col">
        <header className="mobile-bar">
          <button className="sidebar-burger" type="button" onClick={toggleNav}
                  aria-label={navOpen ? "Close menu" : "Open menu"} title="Menu">
            <IconBurger />
          </button>
          <div className="mobile-brand">
            <b>ZERODAY</b>
            <span>Document desk</span>
          </div>
        </header>
        {(loc.pathname === "/" || loc.pathname === "/inbox") && (
          <PageDrop onZip={(file) => { stageZip(file); nav("/settings"); }} />
        )}
        <main className="page"><Outlet /></main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <>
    <A11yControl />
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/comparison" element={<Comparison />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
    </>
  );
}
