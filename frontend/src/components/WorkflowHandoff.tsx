import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

interface WorkflowHandoffProps {
  current: string;
  nextLabel: string;
  nextTo: string;
  note: string;
}

export function WorkflowHandoff({
  current,
  nextLabel,
  nextTo,
  note,
}: WorkflowHandoffProps) {
  return (
    <nav className="workflowHandoff" aria-label={`${current} workflow handoff`}>
      <Link className="secondaryButton" to="/projects">
        <ArrowLeft aria-hidden="true" size={15} />
        Dashboard
      </Link>
      <span>{note}</span>
      <Link className="primaryButton" to={nextTo}>
        {nextLabel}
        <ArrowRight aria-hidden="true" size={15} />
      </Link>
    </nav>
  );
}
