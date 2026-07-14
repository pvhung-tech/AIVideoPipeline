import { Film, Image, Trash2 } from "lucide-react";

import type { MediaClip, TimelineMediaAsset } from "../services/timelineClient";

interface TimelineMediaPickerProps {
  title: string;
  assets: TimelineMediaAsset[];
  selectedContentHash: string | null;
  disabled: boolean;
  onSelect: (contentHash: string | null) => void;
  selectedClip: MediaClip | null;
  onTrim: (start: number, end: number) => void;
}

export function TimelineMediaPicker({
  title,
  assets,
  selectedContentHash,
  disabled,
  onSelect,
  selectedClip,
  onTrim,
}: TimelineMediaPickerProps) {
  const selected = assets.find(
    (asset) => asset.contentHash === selectedContentHash,
  );
  return (
    <section className="mediaPicker" aria-label={`${title} media`}>
      <div className="mediaPickerHeading">
        <span>{title}</span>
        {selected && (
          <button
            className="miniIconButton"
            disabled={disabled}
            title="Remove scene media"
            onClick={() => onSelect(null)}
          >
            <Trash2 aria-hidden="true" size={15} />
          </button>
        )}
      </div>
      {selected?.mediaType === "image" && (
        <img className="mediaPreview" src={selected.uri} alt="Selected scene media" />
      )}
      {selected?.mediaType === "video" && (
        <div className="videoPreview">
          <Film aria-hidden="true" size={24} />
          <span>{selected.fileName}</span>
        </div>
      )}
      <label>
        Cached asset
        <select
          disabled={disabled || assets.length === 0}
          value={selectedContentHash ?? ""}
          onChange={(event) => onSelect(event.target.value || null)}
        >
          <option value="">{assets.length ? "No media" : "Cache is empty"}</option>
          {assets.map((asset) => (
            <option key={asset.contentHash} value={asset.contentHash}>
              {asset.mediaType === "image" ? "Image" : "Video"} · {asset.fileName}
            </option>
          ))}
        </select>
      </label>
      {selected && (
        <div className="assetMeta">
          {selected.mediaType === "image" ? (
            <Image aria-hidden="true" size={14} />
          ) : (
            <Film aria-hidden="true" size={14} />
          )}
          <span>{formatBytes(selected.sizeBytes)}</span>
          <span>{selected.providerIds.join(", ") || "cache"}</span>
        </div>
      )}
      {selected?.mediaType === "video" && selected.durationMilliseconds && selectedClip && (
        <div className="trimControls">
          <label>In (seconds)<input type="number" min="0" step="0.1" value={(selectedClip.sourceStartMilliseconds ?? 0) / 1000} onChange={(event) => onTrim(Math.round(Number(event.target.value) * 1000), selectedClip.sourceEndMilliseconds ?? 0)} /></label>
          <label>Out (seconds)<input type="number" min="0" max={selected.durationMilliseconds / 1000} step="0.1" value={(selectedClip.sourceEndMilliseconds ?? 0) / 1000} onChange={(event) => onTrim(selectedClip.sourceStartMilliseconds ?? 0, Math.round(Number(event.target.value) * 1000))} /></label>
          <small>Source: {(selected.durationMilliseconds / 1000).toFixed(1)}s</small>
        </div>
      )}
    </section>
  );
}

function formatBytes(sizeBytes: number): string {
  if (sizeBytes < 1_024) return `${sizeBytes} B`;
  if (sizeBytes < 1_048_576) return `${(sizeBytes / 1_024).toFixed(1)} KB`;
  return `${(sizeBytes / 1_048_576).toFixed(1)} MB`;
}
