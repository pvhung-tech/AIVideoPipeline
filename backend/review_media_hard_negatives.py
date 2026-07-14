import argparse
import json
import sys
from pathlib import Path

from app.media.deduplication_thresholds import loadMediaDeduplicationThresholds
from app.media.hard_negative_review import (
    applyHardNegativeReview,
    prepareHardNegativeReview,
    summarizeHardNegativeReview,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review near-threshold hard negatives."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("manifest", type=Path)
    prepare.add_argument("queue", type=Path)
    prepare.add_argument("--thresholds", type=Path, required=True)
    prepare.add_argument("--margin", type=float, default=5)
    status = subparsers.add_parser("status")
    status.add_argument("queue", type=Path)
    apply = subparsers.add_parser("apply")
    apply.add_argument("queue", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "prepare":
        summary = prepareHardNegativeReview(
            arguments.manifest.resolve(),
            arguments.queue.resolve(),
            loadMediaDeduplicationThresholds(arguments.thresholds.resolve()),
            arguments.margin,
        )
    elif arguments.command == "apply":
        summary = applyHardNegativeReview(arguments.queue.resolve())
    else:
        summary = summarizeHardNegativeReview(arguments.queue.resolve())
    json.dump(summary.__dict__, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
