import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAppStore } from "../store/appStore";

const navigationItems = [
  { label: "Dashboard", path: "/projects" },
  { label: "Pipeline", path: "/pipeline" },
  { label: "AI", path: "/analysis" },
  { label: "Media", path: "/media" },
  { label: "Timeline", path: "/timeline" },
  { label: "Render", path: "/render" },
  { label: "Settings", path: "/settings" },
];

export function AppLayout() {
  const healthState = useAppStore((state) => state.healthState);
  const checkBackendHealth = useAppStore((state) => state.checkBackendHealth);

  useEffect(() => {
    void checkBackendHealth();
  }, [checkBackendHealth]);

  return (
    <main className="appShell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brandMark">AV</div>
        <nav className="navList">
          {navigationItems.map((item) => (
            <NavLink
              className={({ isActive }) =>
                `navItem${isActive ? " active" : ""}`
              }
              key={item.path}
              to={item.path}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topBar">
          <div>
            <p className="eyebrow">Phase 7</p>
            <h1>AI Video Pipeline Studio</h1>
          </div>
          <BackendStatus healthState={healthState} />
        </header>
        <Outlet />
      </section>
    </main>
  );
}

type HealthState = ReturnType<typeof useAppStore.getState>["healthState"];

function BackendStatus({ healthState }: { healthState: HealthState }) {
  if (healthState.status === "loading") {
    return <span className="status pending">Checking backend</span>;
  }

  if (healthState.status === "offline") {
    return <span className="status offline">{healthState.message}</span>;
  }

  return (
    <span className="status online">
      {healthState.health.appName}: {healthState.health.status}
    </span>
  );
}
