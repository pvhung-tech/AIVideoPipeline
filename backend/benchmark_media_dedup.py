import argparse
import json
import sys
from pathlib import Path

from app.media.fingerprint_benchmark import (
    MediaFingerprintBenchmark,
    loadBenchmarkPairs,
)
from app.media.media_fingerprint_service import MediaFingerprintService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark media fingerprint thresholds."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--ffmpeg-path")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    pairs = loadBenchmarkPairs(arguments.manifest.resolve())
    report = MediaFingerprintBenchmark(
        MediaFingerprintService(arguments.ffmpeg_path, arguments.timeout_seconds)
    ).run(pairs)
    payload = json.dumps(report.toDictionary(), indent=2, ensure_ascii=True)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload + "\n", encoding="utf-8")
    else:
        sys.stdout.write(payload + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
