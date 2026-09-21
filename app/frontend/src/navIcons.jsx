function Svg({ children }) {
  return (
    <svg className="nav-ico" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"
         fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

export function IconBurger() {
  return <Svg><path d="M4 7h16M4 12h16M4 17h16" /></Svg>;
}

export function IconDashboard() {
  return (
    <Svg>
      <rect x="4" y="4" width="7" height="7" rx="1.4" />
      <rect x="13" y="4" width="7" height="7" rx="1.4" />
      <rect x="4" y="13" width="7" height="7" rx="1.4" />
      <rect x="13" y="13" width="7" height="7" rx="1.4" />
    </Svg>
  );
}

export function IconInbox() {
  return (
    <Svg>
      <path d="M4 8l8 6 8-6" />
      <rect x="4" y="6" width="16" height="12" rx="2" />
    </Svg>
  );
}

export function IconCompare() {
  return (
    <Svg>
      <rect x="3.5" y="5" width="7" height="14" rx="1.4" />
      <rect x="13.5" y="5" width="7" height="14" rx="1.4" />
    </Svg>
  );
}

export function IconAudit() {
  return (
    <Svg>
      <path d="M8 4h8a2 2 0 0 1 2 2v14H6V6a2 2 0 0 1 2-2z" />
      <path d="M9 10h6M9 14h6" />
    </Svg>
  );
}

export function IconSettings() {
  return (
    <Svg>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3.5v2.2M12 18.3V20.5M3.5 12h2.2M18.3 12H20.5M6.1 6.1l1.6 1.6M16.3 16.3l1.6 1.6M6.1 17.9l1.6-1.6M16.3 7.7l1.6-1.6" />
    </Svg>
  );
}

export function IconSignOut() {
  return (
    <Svg>
      <path d="M10 6H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4" />
      <path d="M14 8l5 4-5 4M10 12h9" />
    </Svg>
  );
}

export function IconA11y() {
  return (
    <Svg>
      <circle cx="12" cy="5" r="2" />
      <path d="M6 9h12M12 9v5M8 20l4-6 4 6" />
    </Svg>
  );
}
