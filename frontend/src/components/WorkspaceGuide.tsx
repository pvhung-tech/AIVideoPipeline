import { AlertCircle, ArrowRight, Info } from "lucide-react";
import { Link } from "react-router-dom";

type WorkspaceGuideTone = "info" | "warning" | "error";

interface WorkspaceGuideProps {
  title: string;
  message: string;
  actionLabel?: string;
  to?: string;
  tone?: WorkspaceGuideTone;
}

export function WorkspaceGuide({
  title,
  message,
  actionLabel,
  to,
  tone = "info",
}: WorkspaceGuideProps) {
  const Icon = tone === "error" ? AlertCircle : Info;

  return (
    <aside className={`workspaceGuide ${tone}`} aria-label={title}>
      <div className="workspaceGuideIcon">
        <Icon aria-hidden="true" size={18} />
      </div>
      <div className="workspaceGuideBody">
        <h3>{title}</h3>
        <p>{message}</p>
        {actionLabel && to ? (
          <Link className="secondaryButton" to={to}>
            {actionLabel}
            <ArrowRight aria-hidden="true" size={15} />
          </Link>
        ) : null}
      </div>
    </aside>
  );
}
