import { AlertCircle, CheckCircle2, KeyRound, RefreshCw, Settings } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { FingerprintBackfillStatusChip } from "../components/FingerprintBackfillStatusChip";
import { getSetupStatus, type SetupCheck, type SetupStatus } from "../services/setupClient";

export function SettingsPage() {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [message, setMessage] = useState("Loading setup status...");
  const [isLoading, setIsLoading] = useState(false);

  const readyCount = useMemo(
    () => status?.providers.filter((item) => isReadyStatus(item.status)).length ?? 0,
    [status],
  );
  const missingKeyCount = useMemo(
    () => status?.apiKeys.filter((item) => !item.configured).length ?? 0,
    [status],
  );

  useEffect(() => {
    void loadStatus();
  }, []);

  async function loadStatus() {
    setIsLoading(true);
    try {
      const nextStatus = await getSetupStatus();
      setStatus(nextStatus);
      setMessage("Setup status refreshed.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Setup status unavailable");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="settingsWorkspace" aria-label="Settings and setup workspace">
      <header className="settingsWorkspaceHeader">
        <div>
          <p className="eyebrow">Settings</p>
          <h2>Setup providers and runtime checks</h2>
          <p className="timelineMessage" role="status">
            {message}
          </p>
        </div>
        <div className="workspaceHeaderActions">
          <FingerprintBackfillStatusChip />
          <button
            className="iconButton"
            disabled={isLoading}
            onClick={() => void loadStatus()}
            title="Refresh setup"
          >
            <RefreshCw aria-hidden="true" size={18} />
          </button>
        </div>
      </header>

      <div className="settingsSummary">
        <SummaryTile label="Ready providers" value={readyCount} />
        <SummaryTile label="Missing keys" value={missingKeyCount} />
        <SummaryTile label="Setup checks" value={totalChecks(status)} />
      </div>

      <div className="settingsGrid">
        <SettingsPanel
          checks={status?.providers ?? []}
          icon={<Settings aria-hidden="true" size={18} />}
          title="AI providers"
        />
        <SettingsPanel
          checks={status?.apiKeys ?? []}
          icon={<KeyRound aria-hidden="true" size={18} />}
          title="API keys"
        />
        <SettingsPanel
          checks={status?.tools ?? []}
          icon={<CheckCircle2 aria-hidden="true" size={18} />}
          title="Runtime tools"
        />
      </div>
    </section>
  );
}

function SummaryTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="settingsSummaryTile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SettingsPanel({
  checks,
  icon,
  title,
}: {
  checks: SetupCheck[];
  icon: ReactNode;
  title: string;
}) {
  return (
    <section className="settingsPanel">
      <div className="settingsPanelHeading">
        <span>{icon}</span>
        <h3>{title}</h3>
      </div>
      <div className="settingsCheckList">
        {checks.map((check) => (
          <SetupCheckCard check={check} key={check.id} />
        ))}
        {!checks.length && <p className="emptyState">No setup checks available.</p>}
      </div>
    </section>
  );
}

function SetupCheckCard({ check }: { check: SetupCheck }) {
  const ready = isReadyStatus(check.status);
  return (
    <article className={`settingsCheckCard${ready ? " ready" : " attention"}`}>
      <div className="settingsCheckTitle">
        {ready ? (
          <CheckCircle2 aria-hidden="true" size={18} />
        ) : (
          <AlertCircle aria-hidden="true" size={18} />
        )}
        <strong>{check.label}</strong>
        <span>{formatStatus(check.status)}</span>
      </div>
      <p>{check.message}</p>
      <small>{check.hint}</small>
      <dl>
        {check.envVar && (
          <div>
            <dt>Env var</dt>
            <dd>{check.envVar}</dd>
          </div>
        )}
        {check.valuePreview && (
          <div>
            <dt>Value</dt>
            <dd>{check.valuePreview}</dd>
          </div>
        )}
      </dl>
    </article>
  );
}

function totalChecks(status: SetupStatus | null): number {
  if (!status) return 0;
  return status.providers.length + status.apiKeys.length + status.tools.length;
}

function isReadyStatus(status: string): boolean {
  return ["ready", "configured", "path"].includes(status);
}

function formatStatus(status: string): string {
  return status.replace(/_/g, " ");
}
