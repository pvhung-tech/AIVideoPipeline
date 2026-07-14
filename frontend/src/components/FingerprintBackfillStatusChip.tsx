import { AlertCircle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getMediaFingerprintBackfillStatus,
  MediaApiError,
  type FingerprintBackfillJob,
} from "../services/mediaClient";

type ChipTone = "ready" | "active" | "paused" | "attention" | "idle";

export function FingerprintBackfillStatusChip() {
  const [job, setJob] = useState<FingerprintBackfillJob | null>(null);
  const [tone, setTone] = useState<ChipTone>("idle");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const active = job?.status === "queued" || job?.status === "running";
  const label = useMemo(() => statusLabel(job, tone), [job, tone]);
  const title = useMemo(() => statusTitle(job, tone), [job, tone]);

  useEffect(() => {
    void refreshStatus(false);
  }, []);

  useEffect(() => {
    if (!active) return undefined;
    const intervalId = window.setInterval(() => {
      void refreshStatus(false);
    }, 2000);
    return () => window.clearInterval(intervalId);
  }, [active]);

  async function refreshStatus(showRefreshing: boolean) {
    if (showRefreshing) {
      setIsRefreshing(true);
    }
    try {
      const nextJob = await getMediaFingerprintBackfillStatus();
      setJob(nextJob);
      setTone(toneForJob(nextJob));
    } catch (error: unknown) {
      setJob(null);
      setTone(error instanceof MediaApiError && error.code === "NO_ACTIVE_PROJECT" ? "idle" : "attention");
    } finally {
      if (showRefreshing) {
        setIsRefreshing(false);
      }
    }
  }

  return (
    <button
      aria-label={label}
      className={`fingerprintStatusChip ${tone}`}
      onClick={() => void refreshStatus(true)}
      title={title}
      type="button"
    >
      <ChipIcon job={job} isRefreshing={isRefreshing} tone={tone} />
      <span>{label}</span>
    </button>
  );
}

function ChipIcon({
  job,
  isRefreshing,
  tone,
}: {
  job: FingerprintBackfillJob | null;
  isRefreshing: boolean;
  tone: ChipTone;
}) {
  if (isRefreshing || job?.status === "queued" || job?.status === "running") {
    return <Loader2 aria-hidden="true" className="spinIcon" size={14} />;
  }
  if (tone === "attention") {
    return <AlertCircle aria-hidden="true" size={14} />;
  }
  if (tone === "paused") {
    return <RefreshCw aria-hidden="true" size={14} />;
  }
  return <CheckCircle2 aria-hidden="true" size={14} />;
}

function toneForJob(job: FingerprintBackfillJob | null): ChipTone {
  if (!job) return "ready";
  if (job.status === "queued" || job.status === "running") return "active";
  if (job.status === "failed") return "attention";
  if (job.status === "cancelled") return "paused";
  return "ready";
}

function statusLabel(job: FingerprintBackfillJob | null, tone: ChipTone): string {
  if (!job) {
    return tone === "attention" ? "Duplicate check unavailable" : "Duplicate check ready";
  }
  if (job.status === "queued") {
    return "Duplicate check queued";
  }
  if (job.status === "running") {
    return `Duplicate check ${Math.round(job.progressPercent)}%`;
  }
  if (job.status === "failed") {
    return "Duplicate check needs attention";
  }
  if (job.status === "cancelled") {
    return "Duplicate check paused";
  }
  return job.failedCount > 0 ? "Duplicate check finished with issues" : "Duplicate check ready";
}

function statusTitle(job: FingerprintBackfillJob | null, tone: ChipTone): string {
  if (!job) {
    return tone === "attention"
      ? "Could not refresh duplicate-check status."
      : "Cache duplicate detection is up to date.";
  }
  const counts = `${job.processedMedia}/${job.totalMedia} media checked, ${job.updatedMedia} updated`;
  if (job.status === "queued" || job.status === "running") {
    return `Improving cache duplicate detection in the background. ${counts}.`;
  }
  if (job.status === "failed") {
    return job.errorMessage ?? `Duplicate check stopped before finishing. ${counts}.`;
  }
  if (job.status === "cancelled") {
    return `Duplicate check was paused. ${counts}.`;
  }
  return `Cache duplicate detection is up to date. ${counts}.`;
}
